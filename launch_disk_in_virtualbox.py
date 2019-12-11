import traceback

try:
    # Wrap the entire module in a try/except to catch unexpected issues
    # introduced by PyInstaller.
    from _launch_disk_in_virtualbox import main
    main()
except Exception as e:
    traceback.print_exc()
    input("Encountered an error. Press Enter to exit.")
