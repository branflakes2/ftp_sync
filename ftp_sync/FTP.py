import contextlib
import datetime
import logging
import hashlib
import json
import platform
import os

from contextlib import redirect_stdout
from dateutil import parser
from ftplib import FTP, error_perm, error_temp
from pathlib import Path
from tempfile import TemporaryFile

logger = logging.getLogger(__name__)

if platform.system() == 'Windows':
    FTP_SYNC_HOME = Path(str(os.environ.get('UserProfile'))) / "Documents" / "ftp_sync"
else:
    FTP_SYNC_HOME = Path(str(os.environ.get('HOME'))) / ".config" / "ftp_sync"
FTP_SYNC_CONFIG_PATH = FTP_SYNC_HOME / "ftp_sync.yaml"

class Patcher:
    def  to_remote(self, file):
        pass
    def from_remote(self, file):
        pass

class DESMumePatcher(Patcher):
    DESMUME_FOOTER = b'|<--Snip above here to create a raw sav by excluding this DeSmuME savedata footer:\x01\x00\x04\x00\x00\x00\x08\x00\x06\x00\x00\x00\x03\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00|-DESMUME SAVE-|'

    def from_remote(self, file):
        logger.info("Applying DESMume footer")
        return file.read() + self.DESMUME_FOOTER

    def to_remote(self, file):
        logger.info("Removing DESMume footer")
        data = file.read()
        return data[:len(data) - len(self.DESMUME_FOOTER)]


class FTPSync:

    LOCAL_TO_REMOTE = 0
    REMOTE_TO_LOCAL = 1
    DO_NOT_SYNC = 2
    MIN_SAFE_DRIFT = 600
    DATE_FORMAT = "%m_%d_%Y_%H_%M"

    def __init__(self, ftp_helper, backup_dir=FTP_SYNC_HOME / "backup", hash_db_path=FTP_SYNC_HOME / "hash_db.json"):
        if not os.path.exists(FTP_SYNC_HOME):
            os.makedirs(FTP_SYNC_HOME)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        self.ftp_helper = ftp_helper
        self.backup_dir = Path(backup_dir)
        self.hash_db_path = hash_db_path
        if not os.path.exists(hash_db_path):
            self.hash_db = {'local': {}, 'remote': {}}
        else:
            with open(hash_db_path) as f:
                self.hash_db = json.load(f)
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

    def _get_previous_digest(self, path, remote=False):
        if remote:
            return self.hash_db['remote'].get(path)
        else:
            return self.hash_db['local'].get(path)

    def _set_previous_digest(self, path, digest, remote=False):
        if remote:
            self.hash_db['remote'][path] = digest
        else:
            self.hash_db['local'][path] = digest

    def _get_digest(self, path, remote=False, patcher=None):
        if remote:
            try:
                with self.ftp_helper.download_to_tempfile(path, patcher) as f:
                    return hashlib.md5(f.read()).hexdigest()
            except (error_perm, error_temp):
                return None
        else:
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            else:
                return None

    def _get_sync_direction(self, local_path, remote_path, patcher=None):
        lp_previous_hash = self._get_previous_digest(local_path, remote=False)
        rp_previous_hash = self._get_previous_digest(remote_path, remote=True)
        lp_hash = self._get_digest(local_path, remote=False, patcher=patcher)
        rp_hash = self._get_digest(remote_path, remote=True, patcher=patcher)
        logger.debug(f'local: {lp_previous_hash} -> {lp_hash}    remote: {rp_previous_hash} -> {rp_hash}')
        if rp_hash is None and lp_hash is None:
            logger.info("Not syncing: neither path exists")
            return self.DO_NOT_SYNC, None
        elif rp_hash is None and lp_hash is not None:
            logger.info("Syncing local to remote: remote path does not exist")
            return self.LOCAL_TO_REMOTE, lp_hash
        elif rp_hash is not None and lp_hash is None:
            logger.info("Syncing remote to local: local path does not exist")
            return self.REMOTE_TO_LOCAL, rp_hash
        elif lp_previous_hash == rp_previous_hash:
            if rp_hash != rp_previous_hash and lp_hash == lp_previous_hash:
                logger.info("Syncing remote to local: remote file updated")
                return self.REMOTE_TO_LOCAL, rp_hash
            elif rp_hash == rp_previous_hash and lp_hash != lp_previous_hash:
                logger.info("Syncing local to remote: local file updated")
                return self.LOCAL_TO_REMOTE, lp_hash
            elif rp_hash == rp_previous_hash and lp_hash == lp_previous_hash:
                logger.info("Not syncing: neither path updated")
                return self.DO_NOT_SYNC, None
            else:
                logger.info(f"Not syncing: both paths updated. Please manually sync with either the sync_to or sync_from command: {local_path=}, {remote_path=}")
                return self.DO_NOT_SYNC, None
        else:
            logger.info("Not syncing: previous hashes are different. Please manually sync with either the sync_to or sync_from command")
            return self.DO_NOT_SYNC, None

    def backup(self, path, remote=False):
        backup_filename = (self.get_last_modified(path, remote=remote).strftime(self.DATE_FORMAT) + "___" + datetime.datetime.now().strftime(self.DATE_FORMAT))
        if not str(path).startswith('/'):
            path = Path(path).resolve()
        for d in str(path).split('/')[1:]:
            backup_filename += "___" + d
        local_path = self.backup_dir / backup_filename
        logger.info(f"Backing up {remote=} {path} to {backup_filename}")
        if remote:
            self.ftp_helper.download_file(path, local_path)
        else:
            with open(local_path, 'w+b') as dest:
                if os.path.exists(path):
                    with open(path, 'rb') as src:
                        dest.write(src.read())
                else:
                    logger.info("Local path doesn't exist... No use in backing up nothing!")

    def sync_to(self, local_path, remote_path, patcher=None, digest=None):
        local_is_dir = os.path.isdir(local_path)
        remote_is_dir = self.ftp_helper.is_dir(remote_path)
        if local_is_dir and remote_is_dir:
            for file in self.ftp_helper.get_file_list(remote_path):
                filename = file.name
                self.sync_to(local_path / filename, file, patcher=patcher)
        elif not local_is_dir and not remote_is_dir:
            if digest is None:
                digest = self._get_digest(local_path, remote=False)
            self.backup(remote_path, remote=True)
            self.ftp_helper.upload_file(local_path, remote_path, patcher=patcher)
            self._set_previous_digest(local_path, digest, remote=False)
            self._set_previous_digest(remote_path, digest, remote=True)
        else:
            logger.error(f"Cannot sync directory and non-directory: {local_is_dir=}, {remote_is_dir=}")

    def sync_from(self, local_path, remote_path, patcher=None, digest=None):
        local_is_dir = os.path.isdir(local_path)
        remote_is_dir = self.ftp_helper.is_dir(remote_path)
        if local_is_dir and remote_is_dir:
            for file in self.ftp_helper.get_file_list(remote_path):
                filename = file.name
                self.sync_to(local_path / filename, file, patcher=patcher)
        elif not local_is_dir and not remote_is_dir:
            self.backup(local_path, remote=False)
            self.ftp_helper.download_file(remote_path, local_path, patcher=patcher)
            if digest is None:
                digest = self._get_digest(local_path, remote=False)
            self._set_previous_digest(local_path, digest, remote=False)
            self._set_previous_digest(remote_path, digest, remote=True)
        else:
            logger.error(f"Cannot sync directory and non-directory: {local_is_dir=}, {remote_is_dir=}")

    def sync(self, local_path, remote_path, patcher=None, extensions=None):
        logging.info(f"Syncing {local_path} and {remote_path}.")
        local_is_dir = os.path.isdir(local_path)
        remote_is_dir = self.ftp_helper.is_dir(remote_path)
        if local_is_dir and remote_is_dir:
            for file in self.ftp_helper.get_file_list(remote_path):
                filename = file.name
                self.sync(Path(local_path) / filename, file, patcher=patcher)
        if extensions is not None:
            if "local" in extensions and Path(local_path).suffix != extensions["local"]:
                local_path = str(Path(local_path).stem) + extensions["local"]
            if "remote" in extensions and Path(remote_path).suffix != extensions["remote"]:
                remote_path = str(Path(remote_path).stem) + extensions["remote"]
        if not local_is_dir and not remote_is_dir:
            sync_direction, digest = self._get_sync_direction(local_path, remote_path, patcher=patcher)
            if sync_direction == self.LOCAL_TO_REMOTE:
                self.sync_to(local_path, remote_path, patcher=patcher, digest=digest)
            elif sync_direction == self.REMOTE_TO_LOCAL:
                self.sync_from(local_path, remote_path, patcher=patcher, digest=digest)
        else:
            logger.error(f"Cannot sync directory and non-directory: {local_is_dir=}, {remote_is_dir=}")

    def __del__(self):
        if os.path.exists(self.hash_db_path.parent):
            with open(self.hash_db_path, 'w+') as f:
                json.dump(self.hash_db, f)

class FTPHelper:
    def __init__(self, hostname, port=21, user="anonymous", password=""):
        self.ftp_connection = FTP()
        self.ftp_connection.connect(host=hostname, port=port)
        self.ftp_connection.login(user=user, passwd=password)
        self.download_cache = None
        self.download_cache_path = ""

    def _set_download_cache(self, f, path):
        if self.download_cache is not None and path != self.download_cache_path:
            self.download_cache.close()
        self.download_cache = f
        self.download_cache_path = path

    @staticmethod
    def _get_line_filename(line):
            t = line.split()[7]
            return line[line.find(t) + len(t) :].strip()

    def upload_file(self, local_path, remote_path, patcher=None):
        logger.info(f"Uploading {local_path} to {remote_path}")
        if patcher is not None:
            with open(local_path, 'rb') as lf:
                with TemporaryFile() as f:
                    f.write(patcher.to_remote(lf))
                    f.seek(0)
                    self.ftp_connection.storbinary(f"STOR {remote_path}", f)
        else:
            with open(local_path, "rb") as f:
                self.ftp_connection.storbinary(f"STOR {remote_path}", f)

    def download_file(self, remote_path, local_path, patcher=None):
        logger.info(f"Downloading {remote_path} to {local_path}")
        if self.download_cache_path == remote_path and self.download_cache is not None:
            logger.info(f"Using cached download for {remote_path}")
            with open(local_path, "w+b") as lf:
                self.download_cache.seek(0)
                lf.write(self.download_cache.read())
        else:
            if patcher is not None:
                with TemporaryFile() as f:
                    self.ftp_connection.retrbinary(f"RETR {remote_path}", f.write)
                    f.seek(0)
                    with open(local_path, "w+b") as lf:
                        lf.write(patcher.from_remote(f))
            else:
                with open(local_path, "w+b") as f:
                    self.ftp_connection.retrbinary(f"RETR {remote_path}", f.write)

    def download_to_tempfile(self, remote_path, patcher=None):
        if self.download_cache_path == remote_path and self.download_cache is not None:
            logger.info(f"Using cached tempfile for {remote_path}.")
            self.download_cache.seek(0)
            return self.download_cache
        f = TemporaryFile()
        self.ftp_connection.retrbinary(f"RETR {remote_path}", f.write)
        if patcher is not None:
            f.seek(0)
            data = patcher.from_remote(f)
            f.seek(0)
            f.write(data)
        f.seek(0)
        self._set_download_cache(f, remote_path)
        return f

    def copy_file(self, path, new_path):
        with TemporaryFile() as t:
            self.ftp_connection.retrbinary(f"RETR {path}", t.write)
            t.seek(0)
            self.ftp_connection.storbinary(f"STOR {new_path}", t)

    def delete_file(self, path):
        self.ftp_connection.sendcmd(f"DELE {path}")

    def dir(self, d=None):
        with TemporaryFile("w+") as t:
            with redirect_stdout(t):
                if d is None:
                    self.ftp_connection.dir()
                else:
                    self.ftp_connection.dir(d)
            t.seek(0)
            return t.read().strip()

    def is_dir(self, path):
        path = Path(path)
        if path == Path("/"):
            return True
        else:
            listing = self.dir(str(path.parent))
            filename = path.name
            for line in listing.split('\n'):
                if filename == self._get_line_filename(line):
                    return line[0] == "d"
        return False

    def get_file_list(self, d, recurse=False):
        if recurse:
            raise NotImplementedError("Recursive sync not implemented yet")
        else:
            listing = self.dir(d)
            files = []
            for line in listing.strip().split('\n'):
                if line[0] != 'd':
                    files.append(Path(d) / self._get_line_filename(line))
            return files
        

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
            except (error_perm, error_temp):
                logging.warning(f"Path {remote_path} does not exist on remote")
                return None
            pwd = self.dir()
            logger.debug(pwd)
            for line in pwd.split("\n"):
                if line and line_filename(line) == Path(remote_path).name:
                    return parser.parse(" ".join(line.split()[5:8]))

    def __del__(self):
        self.ftp_connection.quit()
