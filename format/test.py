import os
from pathlib import Path
from formatTransform import format
libre_root = Path("/lib/libreoffice")    
soffice_dir = libre_root / "program"  

os.environ["PATH"] = f"{soffice_dir}{os.pathsep}{os.environ['PATH']}"
import os, sys
#from easyofd.easyofd.ofd import something
sys.path.append('/data/preprocessv4/format/EasyOFD')
res=format(Path("./testData/officetest.docx"))
#print(sys.path)