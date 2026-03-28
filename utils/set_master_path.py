import sys
import inspect
from pathlib import Path

def switch_to_app_context():
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    if caller is not None:
        file = caller.f_globals.get('__file__')
        root = Path(file).parent.parent if file else Path.cwd()
        sys.path.insert(0, str(root))
    else:
        print("Unable to determine the caller's file path.")