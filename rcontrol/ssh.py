# This file is part of rcontrol.
#
# rcontrol is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# rcontrol is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with rcontrol. If not, see <http://www.gnu.org/licenses/>.

import paramiko
from rcontrol.streamreader import StreamsReader
from rcontrol.core import CommandTask, BaseSession


class ChannelReader(StreamsReader):
    """
    Specialized reader for paramiko.channel.Channel.
    """
    def _create_readers(self, queue, channel):
        stdout_reader = self._create_stream_reader(channel.makefile('r'),
                                                   queue,
                                                   self.stdout_callback)
        stderr_reader = None
        if not channel.combine_stderr:
            stderr_reader = \
                self._create_stream_reader(channel.makefile_stderr('r'),
                                           queue,
                                           self.stderr_callback)
        return stdout_reader, stderr_reader


class SshExec(CommandTask):
    """
    Execute a remote ssh command.

    The execution starts as soon as the object is created.

    Basically extend a :class:`CommandTask` to pass in a specialized
    stream reader, :class:`ChannelReader`.

    :param session: instance of the :class:`SshSession` responsible of
        this command execution
    :param command: the command to execute (a string)
    :param kwargs: list of argument passed to the base class constructor
    """
    def __init__(self, session, command, **kwargs):
        CommandTask.__init__(self, session, ChannelReader, command, **kwargs)

        transport = self.session.ssh_client.get_transport()
        self._ssh_session = transport.open_session()
        self._ssh_session.set_combine_stderr(self._combine_stderr)

        self._ssh_session.exec_command(command)

        self._reader.start(self._ssh_session)

    def _on_finished(self):
        if not self.timed_out():
            self._set_exit_code(self._ssh_session.recv_exit_status())
        CommandTask._on_finished(self)


def ssh_client(host, username=None, password=None, **kwargs):
    """
    Create a new :class:`paramiko.SSHClient`, connect it and return the
    instance.

    This is a simple wrapper around the connect method that add some good
    defaults when using username/password to connect.
    """
    client = paramiko.SSHClient()
    if username is not None:
        kwargs['username'] = username
    if password is not None:
        kwargs['password'] = password
    if username is not None and password is not None:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs.setdefault('look_for_keys', False)
    client.connect(host, **kwargs)
    return client


class SshSession(BaseSession):
    """
    A specialized ssh session.

    Requires an instance of a connected :class:`paramiko.SSHClient`, as
    returned by :func:`ssh_client`.

    :param client: an instance of a connected :class:`paramiko.SSHClient`
    :param auto_close: if True, automatically close the ssh session when using
        the 'with' statement.
    """
    def __init__(self, client, auto_close=True):
        BaseSession.__init__(self, auto_close=auto_close)
        self.ssh_client = client
        self.sftp = client.open_sftp()

    def open(self, filename, mode='r', bufsize=-1):
        return self.sftp.open(filename, mode=mode, bufsize=bufsize)

    def execute(self, command, **kwargs):
        return SshExec(self, command, **kwargs)

    def close(self):
        self.ssh_client.close()
