import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import sys
import os
import logging

# Configuración de logs
log_dir = r"C:\inetpub\logs\pocdashboard"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "waitress_service.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

class WaitressService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DjangoWaitressService"
    _svc_display_name_ = "Django Waitress Service"
    _svc_description_ = "Runs pocdashboard v0.1 project with Waitress on port 8000."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        logging.info("Stopping service...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            self.process.terminate()
            self.process.wait()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            logging.info("Service starting...")

            # Ruta del proyecto y venv
            project_dir = r"C:\inetpub\pocdashboard"  # <-- Cambiar según tu proyecto
            os.chdir(project_dir)
            python_exe = r"C:\ProgramData\anaconda3\envs\djangoiis\python.exe"  # <-- Python del venv ## No usar python sin un venv (venv, conda, du, el que sea)

            script_path = os.path.join(project_dir, "runwaitress.py")
            logging.info(f"Launching Waitress: {python_exe} {script_path}")

            # Lanzar Waitress
            self.process = subprocess.Popen(
                [python_exe, script_path],
                stdout=None,
                stderr=None
            )

            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        except Exception as e:
            logging.exception("Error starting service: %s", e)
            raise

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(WaitressService)
