"""HTTPS transport with progress tracking."""

from .https_transport import HttpsTransport


class HttpsTransportWithProgress(HttpsTransport):
    """HTTPS transport with progress callback support."""

    def __init__(self, url: str, progress_callback=None):
        """Initialize HTTPS transport with progress tracking.

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
        url = f"{self.url}/git-upload-pack"

        response = self.session.post(
            url,
            data=request,
            headers={'Content-Type': 'application/x-git-upload-pack-request'},
            stream=True
        )
        response.raise_for_status()

        # Stream the response and count bytes with progress updates
        total_bytes = 0
        for chunk in response.iter_content(chunk_size=8192):
            total_bytes += len(chunk)

            # Report progress
            if self.progress_callback:
                self.progress_callback(total_bytes)

        return total_bytes
