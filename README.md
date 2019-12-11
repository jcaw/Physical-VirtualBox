# Physical VirtualBox

Portable utility to boot physical OS installations in VirtualBox (on Windows) so
you don't have to restart.

If you have an OS on a physical drive, add this utility to the same drive (on a
different partition). Double-click it, and it will boot that entire drive in
VirtualBox. Note this OS must be installed on a different _physical disk_ than
the one Windows is running from (not just a different partition).

This utility is designed for a portable installation of Manjaro. The OS is
hard-coded but can be changed easily.

## Usage

Ensure `python` refers to Python 3.7+. Use a virtual environment if you want to
insulate your system installation - `make.bat` will install & update some pip
packages.

1. Run `make.bat`. It will create a self-contained executable
   `launch_disk_in_virtualbox.exe` in `dist`.
2. Create a small partition (50mb or so) on the physical drive you want to boot.
   The partition should be NTFS or FAT32 so Windows can read it. It must be on
   the same _physical disk_ as the OS you want to boot.
3. Move/copy `launch_disk_in_virtualbox.exe` onto the new partition.

Run `launch_disk_in_virtualbox.exe` from its new location as administrator. It
will detect which disk it's being run from, and boot that disk in VirtualBox.

Note that while this will add a new virtual machine to your VM list, you should
not boot it directly - please always boot using `launch_disk_in_virtualbox.exe`.
This recreate the VM every time, and prevent the physical drive from going out
of sync.

This is a portable solution that should work across machines, as long as
VirtualBox is installed (it may need to be on the `PATH`). It's explicitly
designed to boot portable Linux installations without restarting.

## Disclaimer

Using VirtualBox on physical drives is risky. I don't know all the circumstances
under which this could cause data loss and I accept no liability for it. Use at
your own risk.

Don't try and run this utility from the same physical disk as your active
Windows installation. It will try and block you, but the detection may not be
foolproof. If you get past it, you could corrupt the whole disk.

Don't try and use this with exotic drive configurations like RAID or remote
storage unless you know what you're doing - physically connected, single drives
only.
