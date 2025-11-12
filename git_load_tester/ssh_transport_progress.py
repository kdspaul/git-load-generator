"""SSH transport with progress tracking."""

import paramiko
from .ssh_transport import SshTransport


class SshTransportWithProgress(SshTransport):
    """SSH transport with progress callback support."""

    def __init__(self, url: str, progress_callback=None):
        """Initialize SSH transport with progress tracking.

        Args:
            url: Git repository URL
            progress_callback: Optional callback function(bytes_received)
        """
        super().__init__(url)
        self.progress_callback = progress_callback

    def upload_pack(self, request: bytes) -> int:
        """Upload pack with progress tracking.

        Args:
            request: The upload-pack request

        Returns:
            Total bytes received
        """
        client = self._connect()

        try:
            command = f"git-upload-pack '{self.path}'"
            stdin, stdout, stderr = client.exec_command(command)

            # First, read and discard the ref advertisement until flush packet
            buffer = b""
            while True:
                chunk = stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk
                if b"0000" in buffer:
                    break

            # Send our want/done request
            stdin.write(request)
            stdin.flush()
            stdin.channel.shutdown_write()

            # Stream the response and count bytes with progress updates
            total_bytes = 0
            while True:
                chunk = stdout.read(8192)
                if not chunk:
                    break
                total_bytes += len(chunk)

                # Report progress
                if self.progress_callback:
                    self.progress_callback(total_bytes)

            return total_bytes

        finally:
            client.close()
