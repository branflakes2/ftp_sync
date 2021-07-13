import datetime
import logging
import os

from contextlib import redirect_stdout
from dateutil import parser
from ftplib import FTP, error_perm
from pathlib import Path
from tempfile import TemporaryFile

logger = logging.getLogger(__name__)

class FTPSync:

    LOCAL_TO_REMOTE = 0
    REMOTE_TO_LOCAL = 1
    DO_NOT_SYNC = 2
    MIN_SAFE_DRIFT = 600
    DATE_FORMAT = "%m_%d_%Y_%H_%M"

    def __init__(self, ftp_helper, backup_dir=Path(str(os.environ.get('HOME'))) / ".backup"):
        self.ftp_helper = ftp_helper
        self.backup_dir = Path(backup_dir)
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def get_last_modified(self, path, remote=False):
        if not remote:
            if os.path.exists(path):
                return datetime.datetime.fromtimestamp(Path(path).stat().st_mtime)
            else:
                return datetime.datetime.fromtimestamp(0)
        else:
            last_modified = self.ftp_helper.last_modified(path)
            if last_modified is not None:
                return last_modified
            else:
                return datetime.datetime.fromtimestamp(0)

    def _get_sync_direction(self, local_path, remote_path):
        lp_mtime = self.get_last_modified(local_path, remote=False)
        rp_mtime = self.get_last_modified(remote_path, remote=True)
        logger.info(f"Local: {str(lp_mtime)}    Remote: {str(rp_mtime)}: {abs((lp_mtime - rp_mtime).seconds)}")
        if lp_mtime > rp_mtime:
            delta = lp_mtime - rp_mtime
        else:
            delta = rp_mtime - lp_mtime
        if abs(delta.seconds) > self.MIN_SAFE_DRIFT:
            if lp_mtime > rp_mtime:
                return self.LOCAL_TO_REMOTE
            else:
                return self.REMOTE_TO_LOCAL
        else:
            return self.DO_NOT_SYNC

    def backup(self, path, remote=False):
        backup_filename = (self.get_last_modified(path, remote=remote).strftime(self.DATE_FORMAT) + "___" + datetime.datetime.now().strftime(self.DATE_FORMAT))
        if not path.startswith('/'):
            path = Path(path).resolve()
        for d in str(path).split('/')[1:]:
            backup_filename += "___" + d
        local_path = self.backup_dir / backup_filename
        logger.info(f"Backing up {remote=} {path} to {backup_filename}.")
        if remote:
            self.ftp_helper.download_file(path, local_path)
        else:
            with open(local_path, 'w+b') as dest:
                if os.path.exists(path):
                    with open(path, 'rb') as src:
                        dest.write(src.read())
                else:
                    logging.info("Local path doesn't exist... No using in backing up nothing!")

    def sync(self, local_path, remote_path):
        sync_direction = self._get_sync_direction(local_path, remote_path)
        if not sync_direction:
            logger.info(f"Syncing local {local_path} to {remote_path}.")
        elif sync_direction == 1:
            logger.info(f"Syncing remote {remote_path} to {local_path}.")
        else:
            logger.info(f"Not syncing {local_path} and {remote_path}: time to similar: delta < {self.MIN_SAFE_DRIFT}")
        if sync_direction == self.LOCAL_TO_REMOTE:
            self.backup(remote_path, remote=True)
            self.ftp_helper.upload_file(local_path, remote_path)
        elif sync_direction == self.REMOTE_TO_LOCAL:
            self.backup(local_path, remote=False)
            self.ftp_helper.download_file(remote_path, local_path)

class FTPHelper:
    def __init__(self, hostname, port=21, user="anonymous", password=""):
        self.ftp_connection = FTP()
        self.ftp_connection.connect(host=hostname, port=port)
        self.ftp_connection.login(user=user, passwd=password)

    def upload_file(self, local_path, remote_path):
        logging.info(f"Uploading {local_path} to {remote_path}.")
        with open(local_path, "rb") as f:
            self.ftp_connection.storbinary(f"STOR {remote_path}", f)

    def download_file(self, remote_path, local_path):
        logging.info(f"Downloading {remote_path} to {local_path}.")
        with open(local_path, "w+b") as f:
            self.ftp_connection.retrbinary(f"RETR {remote_path}", f.write)

    def copy_file(self, path, new_path):
        with TemporaryFile() as t:
            self.ftp_connection.retrbinary(f"RETR {path}", t.write)
            t.seek(0)
            self.ftp_connection.storbinary(f"STOR {new_path}", t)

    def delete_file(self, path):
        self.ftp_connection.sendcmd(f"DELE {path}")

    def dir(self):
        with TemporaryFile("w+") as t:
            with redirect_stdout(t):
                self.ftp_connection.dir()
            t.seek(0)
            return t.read()

    def last_modified(self, remote_path):
        def line_filename(line):
            t = line.split()[7]
            return line[line.find(t) + len(t) :].strip()

        # Try using the built in command first
        try:
            return parser.parse(self.ftp_connection.sendcmd(f"MDTM {remote_path}"))

        # Otherwise grab from the cwd output
        except error_perm:
            try:
                logger.debug(Path(remote_path))
                logger.debug(Path(remote_path).parent)
                self.ftp_connection.cwd(str(Path(remote_path).parent))
            except error_perm:
                logging.warning(f"Path {remote_path} does not exist on remote.")
                return None
            pwd = self.dir()
            logger.debug(pwd)
            for line in pwd.split("\n"):
                if line and line_filename(line) == Path(remote_path).name:
                    return parser.parse(" ".join(line.split()[5:8]))

    def __del__(self):
        self.ftp_connection.quit()


if __name__ == "__main__":
    helper = FTPHelper("192.168.0.11", 5000)
    helper.copy_file("/BOOT.NDS", "/copy_test")
    print(helper.dir())
    print(helper.last_modified("/BOOT.NDS"))
    print(helper.last_modified("/copy_test"))
    sync = FTPSync(helper)
    print(sync._get_sync_direction("/home/brian/.xsession-errors", "/snemul.cfg"))
    sync.sync("/home/brian/.xsession-errors", "/snemul.cfg")
    helper.delete_file("/copy_test")
    print("*" * 10)
    helper.dir()
