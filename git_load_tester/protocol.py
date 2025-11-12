"""Git protocol implementation (pkt-line format)."""

from typing import List, Tuple, Optional


class PktLine:
    """Git pkt-line format parser and encoder.

    Format: 4-byte hex length (including the 4 bytes) + data
    Special values:
    - "0000" = flush-pkt (end of section)
    - "0001" = delim-pkt (delimiter)
    - "0002" = response-end-pkt
    """

    FLUSH = b"0000"
    DELIM = b"0001"
    RESPONSE_END = b"0002"

    @staticmethod
    def parse(data: bytes) -> List[bytes]:
        """Parse pkt-line formatted data into individual packets.

        Args:
            data: Raw pkt-line formatted data

        Returns:
            List of data packets (excluding flush/delim packets)
        """
        packets = []
        offset = 0

        while offset < len(data):
            if offset + 4 > len(data):
                break

            length_str = data[offset:offset + 4].decode('ascii')
            length = int(length_str, 16)

            if length == 0:  # Flush packet
                offset += 4
                break  # Stop at flush
            elif length == 1 or length == 2:  # Delim or response-end
                offset += 4
                continue
            else:
                if offset + length > len(data):
                    break
                packet_data = data[offset + 4:offset + length]
                packets.append(packet_data)
                offset += length

        return packets

    @staticmethod
    def encode(data: bytes) -> bytes:
        """Encode data into pkt-line format.

        Args:
            data: Data to encode

        Returns:
            Pkt-line formatted data
        """
        length = len(data) + 4
        return f"{length:04x}".encode('ascii') + data

    @staticmethod
    def flush() -> bytes:
        """Return a flush packet."""
        return PktLine.FLUSH


class RefAdvertisement:
    """Git ref advertisement parser."""

    def __init__(self):
        self.refs = {}  # ref_name -> sha
        self.capabilities = []

    @staticmethod
    def parse(packets: List[bytes]) -> 'RefAdvertisement':
        """Parse ref advertisement from pkt-line packets.

        Args:
            packets: List of pkt-line packets

        Returns:
            RefAdvertisement object
        """
        adv = RefAdvertisement()

        for i, packet in enumerate(packets):
            line = packet.decode('utf-8', errors='ignore').strip()

            if not line:
                continue

            # First line contains capabilities after null byte
            if i == 0 and '\x00' in line:
                ref_part, cap_part = line.split('\x00', 1)
                parts = ref_part.split()
                if len(parts) >= 2:
                    sha, ref_name = parts[0], parts[1]
                    adv.refs[ref_name] = sha
                adv.capabilities = cap_part.split()
            else:
                # Subsequent lines are just "<sha> <ref>"
                parts = line.split()
                if len(parts) >= 2:
                    sha, ref_name = parts[0], parts[1]
                    adv.refs[ref_name] = sha

        return adv

    def default_ref(self) -> Optional[Tuple[str, str]]:
        """Get the default ref to clone (HEAD, main, master, or first branch).

        Returns:
            Tuple of (ref_name, sha) or None
        """
        # Try HEAD first
        if 'HEAD' in self.refs:
            return ('HEAD', self.refs['HEAD'])

        # Try main/master
        if 'refs/heads/main' in self.refs:
            return ('refs/heads/main', self.refs['refs/heads/main'])
        if 'refs/heads/master' in self.refs:
            return ('refs/heads/master', self.refs['refs/heads/master'])

        # Return first branch
        for ref_name, sha in self.refs.items():
            if ref_name.startswith('refs/heads/'):
                return (ref_name, sha)

        return None


def build_clone_request(want_shas: List[str]) -> bytes:
    """Build a complete upload-pack request for a clone operation.

    Args:
        want_shas: List of SHA-1 hashes to request

    Returns:
        Complete request bytes
    """
    # Hardcoded client capabilities
    capabilities = "multi_ack_detailed side-band-64k thin-pack ofs-delta agent=git-load-tester-python/0.1.0"

    request = b""

    # Send want lines (first one includes capabilities)
    for i, sha in enumerate(want_shas):
        if i == 0:
            want_line = f"want {sha} {capabilities}\n".encode('utf-8')
        else:
            want_line = f"want {sha}\n".encode('utf-8')
        request += PktLine.encode(want_line)

    # Send flush to end wants section
    request += PktLine.flush()

    # For a clone, we have no objects, so send done immediately
    done_line = b"done\n"
    request += PktLine.encode(done_line)

    return request
