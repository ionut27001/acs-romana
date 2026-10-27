"""Reader/writer for AC Shadows LocalizationPackage files, keeping Ubisoft's own string dictionary.

AnvilToolkit's writer rebuilds the dictionary as single characters with MaxIndexSize 255; the game crashed on such a
package. This writer keeps the original fragment table (a byte-pair style dictionary) and MaxIndexSize, appends only
characters that are missing, and encodes each string greedily with the longest known fragment.

Layout (as read by AnvilToolkit's LocalizationPackage.Read for Shadows):
  prefix ... u32 magic 0xD28389B5, i32 payload length, payload (big endian), suffix
  payload: u16 MaxIndexSize, u16 fragment count, fragments [u16 rightIndexOrChar, u16 leftIndex] ...,
           u16 table count, tables [u64 FirstEntryID, u32 HeadersOffset, u32 EntriesOffset] ...,
           at EntriesOffset: u16 n, u16 end0, n * [u16 idDelta, u16 endOffset]   (end offsets are cumulative)
           at HeadersOffset: the code bytes of every entry in order
  code: b < Max -> fragment[b+1]; b == 255 -> fragment[i16 + 1]; else ((b << 8) | next) - Max*255 -> fragment[x+1]
"""
import struct

MAGIC = 0xD28389B5


class Package:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.magic_at = raw.index(struct.pack("<I", MAGIC))
        (length,) = struct.unpack_from("<i", raw, self.magic_at + 4)
        self.payload_at = self.magic_at + 8
        self.prefix = raw[:self.magic_at + 4]
        self.suffix = raw[self.payload_at + length:]
        p = raw[self.payload_at:self.payload_at + length]
        self.max_index, count = struct.unpack_from(">HH", p, 0)
        self.frags = [struct.unpack_from(">HH", p, 4 + 4 * i) for i in range(count)]  # (rightOrChar, left)
        pos = 4 + 4 * count
        (ntables,) = struct.unpack_from(">H", p, pos)
        pos += 2
        heads = [struct.unpack_from(">QII", p, pos + 16 * t) for t in range(ntables)]
        self.table_header_end = pos + 16 * ntables
        self.frag_str = [None] * count
        self.tables = []  # [(first_id, [(id, text)])]
        for first, hdr_off, ent_off in heads:
            (n,) = struct.unpack_from(">H", p, ent_off)
            ends = [struct.unpack_from(">H", p, ent_off + 2)[0]]
            ids = [first]
            for k in range(n):
                d, e = struct.unpack_from(">HH", p, ent_off + 4 + 4 * k)
                ids.append(first + d)
                ends.append(e)
            pos, start, rows = hdr_off, 0, []
            for sid, end in zip(ids, ends):
                text, pos = self._decode(p, pos, hdr_off + end)
                rows.append((sid, text))
            self.tables.append((first, rows))

    def fragment(self, i):
        if self.frag_str[i] is None:
            right, left = self.frags[i]
            if left == 0 and right == 0:
                s = ""
            elif left == 0:
                s = chr(right)
            else:
                s = self.fragment(left) + self.fragment(right)
            self.frag_str[i] = s
        return self.frag_str[i]

    def _decode(self, p, pos, end):
        out = []
        mask = self.max_index * 255
        while pos < end:
            b = p[pos]
            pos += 1
            if b < self.max_index:
                out.append(self.fragment(b + 1))
            elif b == 255:
                (i,) = struct.unpack_from(">h", p, pos)
                pos += 2
                out.append(self.fragment(i + 1))
            else:
                x = ((b << 8) | p[pos]) - mask
                pos += 1
                out.append(self.fragment(x + 1))
        return "".join(out), pos

    def strings(self):
        return {sid: text for _, rows in self.tables for sid, text in rows}

    # ---- writing -------------------------------------------------------------------------------------------------
    def _code(self, i):
        """Bytes for fragment index i (fragment[i]), mirroring the decoder."""
        x = i - 1
        if x < self.max_index:
            return bytes([x])
        v = x + self.max_index * 255  # two-byte form: first byte in [max_index, 254]
        if v >> 8 < 255:
            return bytes([v >> 8, v & 0xFF])
        return b"\xff" + struct.pack(">h", x)

    def encode(self, new_strings: dict) -> bytes:
        frags = list(self.frags)
        by_str = {}
        for i in range(1, len(frags)):
            by_str.setdefault(self.fragment(i), i)
        # characters never seen in the original dictionary become new single-char fragments at the end
        for text in new_strings.values():
            for ch in text:
                if ch not in by_str:
                    if ord(ch) > 0xFFFF:
                        raise ValueError(f"character outside the BMP: {ch!r}")
                    frags.append((ord(ch), 0))
                    by_str[ch] = len(frags) - 1
                    self.frag_str.append(ch)
        if len(frags) > 0x8000:
            raise ValueError("too many fragments for the i16 escape")
        maxlen = max(len(s) for s in by_str)
        tables_out = []
        for first, rows in self.tables:
            codes, ends, total = [], [], 0
            for sid, old in rows:
                text = new_strings.get(sid, old)
                # optimal parse: fewest code bytes; ties prefer the lower fragment index
                n = len(text)
                best = [None] * (n + 1)  # best[k] = (bytes, fragment indexes) to encode text[k:]
                best[n] = (0, [])
                for k in range(n - 1, -1, -1):
                    cand = None
                    for L in range(1, min(maxlen, n - k) + 1):
                        i = by_str.get(text[k:k + L])
                        if i is None or best[k + L] is None:
                            continue
                        cost = len(self._code(i)) + best[k + L][0]
                        if cand is None or cost < cand[0]:
                            cand = (cost, [i] + best[k + L][1])
                    best[k] = cand
                buf = bytearray(b"".join(self._code(i) for i in best[0][1]))
                total += len(buf)
                if total > 0xFFFF:
                    raise ValueError(f"table {first} exceeds 65535 code bytes")
                codes.append(bytes(buf))
                ends.append(total)
            tables_out.append((first, rows, codes, ends))
        # payload
        out = bytearray(struct.pack(">HH", self.max_index, len(frags)))
        for right, left in frags:
            out += struct.pack(">HH", right, left)
        out += struct.pack(">H", len(tables_out))
        head_pos = len(out)
        out += bytes(16 * len(tables_out))
        # Ubisoft's layout: every entry table first, then every block of string codes (not interleaved)
        ent_offs = []
        for first, rows, codes, ends in tables_out:
            ent_offs.append(len(out))
            out += struct.pack(">HH", len(rows) - 1, ends[0])
            for (sid, _), end in zip(rows[1:], ends[1:]):
                out += struct.pack(">HH", sid - first, end)
        heads = []
        for (first, rows, codes, ends), ent_off in zip(tables_out, ent_offs):
            heads.append((first, len(out), ent_off))
            for c in codes:
                out += c
        for t, (first, hdr_off, ent_off) in enumerate(heads):
            struct.pack_into(">QII", out, head_pos + 16 * t, first, hdr_off, ent_off)
        return self.prefix + struct.pack("<i", len(out)) + bytes(out) + self.suffix


if __name__ == "__main__":
    import sys
    raw = open(sys.argv[1], "rb").read()
    pkg = Package(raw)
    s = pkg.strings()
    print(f"max_index {pkg.max_index}, {len(pkg.frags)} fragments, {len(pkg.tables)} tables, {len(s)} strings")
    again = pkg.encode({})
    print("re-encode identical to original:", again == raw, f"({len(again)} vs {len(raw)} bytes)")
    if again != raw:
        print("decodes identically:", Package(again).strings() == s)
