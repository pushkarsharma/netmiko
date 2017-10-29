from __future__ import print_function
from __future__ import unicode_literals
import re
import time
import os
from netmiko.cisco_base_connection import CiscoSSHConnection
from netmiko.cisco_base_connection import CiscoFileTransfer


class CiscoNxosSSH(CiscoSSHConnection):

    def session_preparation(self):
        """Prepare the session after the connection has been established."""
        self._test_channel_read(pattern=r'[>#]')
        self.ansi_escape_codes = True
        self.set_base_prompt()
        self.disable_paging()
        # Clear the read buffer
        time.sleep(.3 * self.global_delay_factor)
        self.clear_buffer()

    def normalize_linefeeds(self, a_string):
        """Convert '\r\n' or '\r\r\n' to '\n, and remove extra '\r's in the text."""
        newline = re.compile(r'(\r\r\n|\r\n)')
        return newline.sub(self.RESPONSE_RETURN, a_string).replace('\r', '')


class CiscoNxosFileTransfer(CiscoFileTransfer):
    """Cisco NXOS SCP File Transfer driver."""
    def __init__(self, ssh_conn, source_file, dest_file, file_system=None, direction='put'):
        self.ssh_ctl_chan = ssh_conn
        self.source_file = source_file
        self.dest_file = dest_file
        self.direction = direction

        if file_system:
            self.file_system = file_system
        else:
            raise ValueError("Destination file system must be specified for NX-OS")

        if direction == 'put':
            self.source_md5 = self.file_md5(source_file)
            self.file_size = os.stat(source_file).st_size
        elif direction == 'get':
            self.source_md5 = self.remote_md5(remote_file=source_file)
            self.file_size = self.remote_file_size(remote_file=source_file)
        else:
            raise ValueError("Invalid direction specified")

    def remote_space_available(self, search_pattern=r"(\d+) bytes free"):
        """Return space available on remote device."""
        return super(CiscoNxosFileTransfer, self).remote_space_available(
            search_pattern=search_pattern
        )

    def verify_space_available(self, search_pattern=r"(\d+) bytes free"):
        """Verify sufficient space is available on destination file system (return boolean)."""
        return super(CiscoNxosFileTransfer, self).verify_space_available(
            search_pattern=search_pattern
        )

    def check_file_exists(self, remote_cmd=""):
        """Check if the dest_file already exists on the file system (return boolean)."""
        raise NotImplementedError

    def remote_file_size(self, remote_cmd="", remote_file=None):
        """Get the file size of the remote file."""
        if remote_file is None:
            if self.direction == 'put':
                remote_file = self.dest_file
            elif self.direction == 'get':
                remote_file = self.source_file

        if not remote_cmd:
            remote_cmd = "dir {}/{}".format(self.file_system, remote_file)

        remote_out = self.ssh_ctl_chan.send_command(remote_cmd)
        # Match line containing file name
        escape_file_name = re.escape(remote_file)
        pattern = r".*({}).*".format(escape_file_name)
        match = re.search(pattern, remote_out)
        if match:
            file_size = match.group(0)
            file_size = file_size.split()[0]

        if 'No such file or directory' in remote_out:
            raise IOError("Unable to find file on remote system")
        else:
            return int(file_size)

    @staticmethod
    def process_md5(md5_output, pattern=r"= (.*)"):
        """Not needed on NX-OS."""
        raise NotImplementedError

    def remote_md5(self, base_cmd='show file', remote_file=None):
        if remote_file is None:
            if self.direction == 'put':
                remote_file = self.dest_file
            elif self.direction == 'get':
                remote_file = self.source_file
        remote_md5_cmd = "{} {}{} md5sum".format(base_cmd, self.file_system, remote_file)
        return self.ssh_ctl_chan.send_command(remote_md5_cmd, delay_factor=3.0)

    def enable_scp(self, cmd=None):
        raise NotImplementedError

    def disable_scp(self, cmd=None):
        raise NotImplementedError
