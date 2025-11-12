"""SSH transport for git protocol."""

import paramiko
import re
from typing import Tuple
from .protocol import PktLine, RefAdvertisement, build_clone_request


class SshTransport:
    """SSH transport for git protocol."""

    def __init__(self, url: str):
        """Initialize SSH transport.

        Args:
            url: Git repository URL (git@host:path or ssh://user@host/path)

        Raises:
            ValueError: If URL format is invalid
        """
        self.url = url
        self.host, self.user, self.path, self.port = self._parse_ssh_url(url)

    @staticmethod
    def _parse_ssh_url(url: str) -> Tuple[str, str, str, int]:
        """Parse SSH URL into components.

        Supported formats:
        - git@github.com:user/repo.git
        - ssh://git@github.com/user/repo.git
        - ssh://git@github.com:22/user/repo.git

        Args:
            url: SSH URL

        Returns:
            Tuple of (host, user, path, port)

        Raises:
            ValueError: If URL format is invalid
        """
        if url.startswith('ssh://'):
            # ssh://user@host:port/path
            url_no_scheme = url[6:]  # Remove "ssh://"

            if '/' not in url_no_scheme:
                raise ValueError(f"Invalid SSH URL format: {url}")

            user_host, path = url_no_scheme.split('/', 1)

            if '@' not in user_host:
                raise ValueError(f"SSH URL must contain user@host: {url}")

            user, host_port = user_host.split('@', 1)

            if ':' in host_port:
                host, port_str = host_port.rsplit(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    port = 22
            else:
                host = host_port
                port = 22

            path = '/' + path

        elif '@' in url and ':' in url:
            # git@host:path
            if '://' in url:
                raise ValueError(f"Invalid SSH URL format: {url}")

            user_host, path = url.split(':', 1)

            if '@' not in user_host:
                raise ValueError(f"SSH URL must contain user@host: {url}")

            user, host = user_host.split('@', 1)
            port = 22

            # Ensure path starts with /
            if not path.startswith('/'):
                path = '/' + path

        else:
            raise ValueError(f"Unsupported SSH URL format: {url}")

        return (host, user, path, port)

    def _connect(self) -> paramiko.SSHClient:
        """Connect to SSH server.

        Returns:
            Connected SSHClient

        Raises:
            Exception: If connection fails
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect using SSH agent or keys
        client.connect(
            self.host,
            port=self.port,
            username=self.user,
            timeout=10
        )

        return client

    def discover_refs(self) -> RefAdvertisement:
        """Discover refs from remote repository.

        Returns:
            RefAdvertisement object

        Raises:
            Exception: If operation fails
        """
        client = self._connect()

        try:
            command = f"git-upload-pack '{self.path}'"
            stdin, stdout, stderr = client.exec_command(command)

            # Read ref advertisement until flush packet
            buffer = b""
            while True:
                chunk = stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # Check if we have a flush packet
                if b"0000" in buffer:
                    # Find the position of flush and stop reading
                    flush_pos = buffer.find(b"0000")
                    buffer = buffer[:flush_pos + 4]
                    break

            # Parse pkt-line format
            packets = PktLine.parse(buffer)

            return RefAdvertisement.parse(packets)

        finally:
            client.close()

    def upload_pack(self, request: bytes) -> int:
        """Upload pack (fetch objects from remote).

        Args:
            request: The upload-pack request

        Returns:
            Total bytes received

        Raises:
            Exception: If operation fails
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
            stdin.channel.shutdown_write()  # Close stdin to signal we're done writing

            # Stream the response and count bytes without materializing
            total_bytes = 0
            while True:
                chunk = stdout.read(8192)
                if not chunk:
                    break
                total_bytes += len(chunk)
                # Intentionally NOT storing the data - just counting bytes

            return total_bytes

        finally:
            client.close()

    def clone(self) -> int:
        """Perform a complete clone operation.

        Returns:
            Total bytes received

        Raises:
            Exception: If operation fails
        """
        # Step 1: Discover refs
        refs = self.discover_refs()

        # Step 2: Pick a ref to clone
        default_ref = refs.default_ref()
        if not default_ref:
            raise Exception("No refs found in repository")

        ref_name, sha = default_ref

        # Step 3: Build clone request
        request = build_clone_request([sha])

        # Step 4: Upload pack (receive data)
        bytes_received = self.upload_pack(request)

        return bytes_received
