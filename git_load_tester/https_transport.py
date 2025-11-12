"""HTTPS transport for git protocol."""

import requests
from typing import Optional
from .protocol import PktLine, RefAdvertisement, build_clone_request


class HttpsTransport:
    """HTTPS transport for git protocol (smart HTTP)."""

    def __init__(self, url: str):
        """Initialize HTTPS transport.

        Args:
            url: Git repository URL (https://...)
        """
        self.url = url.rstrip('/')
        if not self.url.endswith('.git'):
            self.url += '.git'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'git-load-tester-python/0.1.0',
        })

    def discover_refs(self) -> RefAdvertisement:
        """Discover refs from remote repository.

        Returns:
            RefAdvertisement object

        Raises:
            Exception: If request fails
        """
        url = f"{self.url}/info/refs?service=git-upload-pack"

        response = self.session.get(url)
        response.raise_for_status()

        data = response.content

        # Skip the service line and flush packet at the beginning
        # Format: "001e# service=git-upload-pack\n0000<refs>"
        offset = 0

        # Skip first packet (service line)
        if data[offset:offset+4] == b'001e':
            offset += 4 + 26  # 4 bytes length + 26 bytes "# service=git-upload-pack\n"

        # Skip flush packet
        if data[offset:offset+4] == b'0000':
            offset += 4

        # Parse remaining pkt-line format (the actual refs)
        ref_data = data[offset:]
        packets = PktLine.parse(ref_data)

        return RefAdvertisement.parse(packets)

    def upload_pack(self, request: bytes) -> int:
        """Upload pack (fetch objects from remote).

        Args:
            request: The upload-pack request

        Returns:
            Total bytes received

        Raises:
            Exception: If request fails
        """
        url = f"{self.url}/git-upload-pack"

        response = self.session.post(
            url,
            data=request,
            headers={'Content-Type': 'application/x-git-upload-pack-request'},
            stream=True
        )
        response.raise_for_status()

        # Stream the response and count bytes without materializing
        total_bytes = 0
        for chunk in response.iter_content(chunk_size=8192):
            total_bytes += len(chunk)
            # Intentionally NOT storing the data - just counting bytes

        return total_bytes

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
