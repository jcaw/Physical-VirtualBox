"""Boot this script's physical disk in a VirtualBox.

Designed to be placed on an external drive for a portable, bootable linux that
can also be booted in a VirtualBox for convenience.

Don't run this script on weird configurations, e.g. RAID. It's designed for a
direct partition on a single disk (really, for an external SSD).

"""


import os
import inspect
import platform
import ctypes
import subprocess
import shutil
import math
from functools import wraps

import wmi
import psutil


# Arch is the OS type for Manjaro (as of VirtualBox 6.0.14)
VIRTUALBOX_OS_TYPE = "ArchLinux_64"

# Folder where our temporary files will be stored.
APP_FOLDER_SHORT = "PortableLinuxBooter"
# Name of the virtual disk file that will link to the physical disk.
VIRTUAL_DISK_FILE = "linked_manjaro_drive.vmdk"
# Name of the temporary virtual machine dedicated to this drive. Only include
# chars that are valid in windows filenames.
VIRTUAL_MACHINE_NAME = "portable-manjaro-DO-NOT-BOOT-FROM-GUI"

# Max amount of VRAM we can assign to a machine in virtualbox.
VIRTUALBOX_VRAM_LIMIT = 256


#############################################################################


APP_FOLDER = os.path.join(os.getenv("APPDATA"), APP_FOLDER_SHORT)

C = wmi.WMI()


# From https://stackoverflow.com/a/12377059/3255378
def listify(fn=None, wrapper=list):
    """A decorator which wraps a function's return value in ``list(...)``.

    Useful when an algorithm can be expressed more cleanly as a generator but
    the function should return an list.

    Example::

        >>> @listify
        ... def get_lengths(iterable):
        ...     for i in iterable:
        ...         yield len(i)
        >>> get_lengths(["spam", "eggs"])
        [4, 4]
        >>>
        >>> @listify(wrapper=tuple)
        ... def get_lengths_tuple(iterable):
        ...     for i in iterable:
        ...         yield len(i)
        >>> get_lengths_tuple(["foo", "bar"])
        (3, 3)
    """
    def listify_return(fn):
        @wraps(fn)
        def listify_helper(*args, **kw):
            return wrapper(fn(*args, **kw))
        return listify_helper
    if fn is None:
        return listify_return
    return listify_return(fn)


@listify
def _logical_drives(physical_disk):
    for partition in physical_disk.associators("Win32_DiskDriveToDiskPartition"):
        for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
            yield physical_disk, logical_disk


@listify
def _logical_to_physical():
    """Map all logical disks to their physical drives."""
    for physical_disk in C.Win32_DiskDrive():
        yield from _logical_drives(physical_disk)


# Somewhat slow to gather. Cache this once.
DRIVE_MAPPING = _logical_to_physical()


def _current_file():
    return inspect.getfile(inspect.currentframe())


def _expand_path(path):
    return os.path.abspath(path)


def _get_physical_disk(path):
    """Get the name of the physical disk where `path` is."""
    path = _expand_path(path)
    target_drive, _ = os.path.splitdrive(path)
    for disk, drive in DRIVE_MAPPING:
        if target_drive.upper() == drive.DeviceID.upper():
            if disk.name:
                return disk.name
            else:
                raise RuntimeError(
                    'No physical disk found for drive "{}"'.format(target_drive)
                )
    raise RuntimeError(
        'Disk not found for (drive, path): ("{}", "{}")'.format(target_drive, path)
    )


def _running_as_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _create_virtual_link(vboxmanage_path, image_path, disk_name):
    print("Creating physical drive link")
    subprocess.run(
        [
            vboxmanage_path,
            "internalcommands",
            "createrawvmdk",
            "-filename",
            image_path,
            "-rawdisk",
            disk_name,
        ],
        check=True,
    )


def _create_virtual_machine(vboxmanage_path, name, os_type):
    # TODO: Set VM description
    print("Creating virtual machine")
    subprocess.run(
        [
            vboxmanage_path,
            "createvm",
            "--name",
            name,
            "--ostype",
            os_type,
            "--register",
        ],
        check=True,
    )
    print("Adding SATA Controller")
    subprocess.run(
        [
            vboxmanage_path,
            "storagectl",
            name,
            "--name",
            "SATA Controller",
            "--add",
            "sata",
            "--controller",
            "IntelAHCI",
        ],
        check=True,
    )
    print("Enabling I/O APC (required for 64-bit and multicore)")
    subprocess.run([vboxmanage_path, "modifyvm", name, "--ioapic", "on"], check=True)
    # FIXME: How to enable host-only from command line? This fails to boot.
    # print("Setting network config")
    # subprocess.run([vboxmanage_path, "modifyvm", name, "--nic2", "hostonly"], check=True)


def _link_virtual_drive(vboxmanage_path, machine_name, vmdk_path):
    print("Linking virtual drive")
    subprocess.run(
        [
            vboxmanage_path,
            "storageattach",
            machine_name,
            "--storagectl",
            "SATA Controller",
            "--port",
            "0",
            "--device",
            "0",
            "--type",
            "hdd",
            "--medium",
            vmdk_path,
        ],
        check=True,
    )


def _set_non_rotational(vboxmanage_path, machine_name):
    """Tell the machine the vhdk is non-rotational.

    This has a few effects, for example Linux won't use it for entropy.

    """
    subprocess.run(
        [
            vboxmanage_path,
            "setextradata",
            machine_name,
            "VBoxInternal/Devices/ahci/0/Config/Port0/NonRotational",
            "1",
        ],
        check=True,
    )


def _set_resources(vboxmanage_path, vm_name, memory=1024, vram=128, cpus=1):
    print("Setting resources for the VM.")
    print(f"  Memory: {memory} MB,  VRAM: {vram} MB,  CPUs: {cpus}")
    subprocess.run(
        [
            vboxmanage_path,
            "modifyvm",
            vm_name,
            "--memory",
            str(memory),
            "--vram",
            str(vram),
            "--cpus",
            str(cpus),
        ],
        check=True,
    )


def _set_resources_dynamic(vboxmanage_path, vm_name):
    """Set the resources for a VM based on those available."""
    total_cores = psutil.cpu_count(logical=True)
    cores_to_use = math.floor(float(total_cores) / 2)
    cores_to_use = max(cores_to_use, 1)

    free_ram_bytes = psutil.virtual_memory().available
    print("This much free ram: {}".format(free_ram_bytes))
    free_ram_megabytes = round(free_ram_bytes / (1024 ** 2))
    print("Free ram megabytes: {}".format(free_ram_megabytes))
    if free_ram_megabytes < 1024:
        raise RuntimeError(
            f"Not enough RAM ({free_ram} MB available, need at least "
            "1024 MB). Aborting."
        )
    ram_to_use = math.floor(float(free_ram_megabytes) / 2)

    # vram is allocated from RAM, not the video card - allocate it from the
    # remaining free memory.
    vram_to_use = math.floor(float(free_ram_megabytes) / 6)
    # At the time of writing (09/12/2019), VirtualBox has a hard limit on VRAM
    # of 256 MB. Can't go over.
    vram_to_use = min(vram_to_use, VIRTUALBOX_VRAM_LIMIT)

    _set_resources(vboxmanage_path, vm_name, ram_to_use, vram_to_use, cores_to_use)


def _boot_vm(vboxmanage_path, name):
    # TODO: Delete the VM after it's closed? Can we do close hooks like that?
    subprocess.run([vboxmanage_path, "startvm", name, "--type", "gui"], check=True)


def _remove_existing_vm(vboxmanage_path, name):
    print("Removing existing VM, if it exists.")
    subprocess.run([vboxmanage_path, "unregistervm", name, "--delete"])
    # HACK: Manually clean settings in case of an unclean removal.
    vm_profile_path = os.path.expandvars(
        f"%USERPROFILE%/VirtualBox VMs/{VIRTUAL_MACHINE_NAME}"
    )
    if os.path.isdir(vm_profile_path):
        print("! MANUALLY REMOVING UNCLEAN PATH")
        shutil.rmtree(vm_profile_path)


def _ensure_not_running(vboxmanage_path, machine_name):
    result = subprocess.run(
        ["vboxmanage", "list", "runningvms"], capture_output=True, check=True
    )
    if machine_name in result.stdout.decode("utf-8"):
        raise RuntimeError(
            f"{VIRTUAL_MACHINE_NAME} already running. Please terminate it first."
        )
    for process in psutil.process_iter(attrs=["name"]):
        # Seems that "VirtualBox.exe" specifically refers to the manager - VMs
        # run under "VirtualBoxVM.exe"
        if process.info["name"].lower() == "virtualbox.exe":
            raise RuntimeError(
                "The VirtualBox Manager is running. Please close it first "
                "(you don't need to close your VMs - just the manager)."
            )


def _is_on_path(exe_name):
    result = subprocess.run(["which", exe_name], capture_output=True)
    return result.returncode == 0


def _default_virtualbox_path():
    # TODO: Dynamically get VirtualBox install location.
    return os.path.expandvars("%PROGRAMFILES%/Oracle/VirtualBox/VBoxManage.exe")


def _find_vboxmanage():
    exe_name = "VBoxManages"
    if _is_on_path(exe_name):
        print("VBoxManage found on PATH")
        return exe_name
    else:
        default_install_path = _default_virtualbox_path()
        if os.path.isfile(default_install_path):
            print(
                f'VBoxManage found at: "{default_install_path}", using this ' "version."
            )
            return default_install_path
        else:
            raise RuntimeError(
                "Could not find VBoxManage. Please install VirtualBox "
                "& add it to the PATH."
            )


def main():
    if not platform.system() == "Windows":
        raise OSError("Only works on Windows.")
    if not _running_as_admin():
        raise OSError("Please run as admin.")
    vboxmanage_path = _find_vboxmanage()

    current_file = _current_file()
    print('Script location:        "{}"'.format(current_file))
    script_disk = _get_physical_disk(current_file)
    print('Script\'s physical disk: "{}"'.format(script_disk))
    windows_disk = _get_physical_disk(os.getenv("SystemDrive"))
    print('Windows physical disk:  "{}"'.format(windows_disk))

    if script_disk.upper() == windows_disk.upper():
        raise RuntimeError(
            "Script is running from the same physical disk as Windows. "
            "Attaching the active boot disk to VirtualBox may result in "
            "catastrophic data loss. Aborting."
        )

    # Tiny possibility of a race after this if the VM is touched elsewhere.
    # Don't worry about it.
    _ensure_not_running(vboxmanage_path, VIRTUAL_MACHINE_NAME)

    # We recreate the virtual machine every time to ensure the drive is always
    # connected correctly, and anything cached is deleted.
    _remove_existing_vm(vboxmanage_path, VIRTUAL_MACHINE_NAME)
    if os.path.isdir(APP_FOLDER):
        print("Found existing virtual machine. Deleting.")
        shutil.rmtree(APP_FOLDER)
    os.mkdir(APP_FOLDER)

    virtual_image = os.path.join(APP_FOLDER, VIRTUAL_DISK_FILE)

    _create_virtual_link(vboxmanage_path, virtual_image, script_disk)
    _create_virtual_machine(vboxmanage_path, VIRTUAL_MACHINE_NAME, VIRTUALBOX_OS_TYPE)
    _link_virtual_drive(vboxmanage_path, VIRTUAL_MACHINE_NAME, virtual_image)
    _set_resources_dynamic(vboxmanage_path, VIRTUAL_MACHINE_NAME)
    _boot_vm(vboxmanage_path, VIRTUAL_MACHINE_NAME)
