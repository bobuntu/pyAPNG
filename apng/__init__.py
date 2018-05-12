#! python3

"""This is an APNG module, which can create apng file from pngs

Reference:
http://littlesvr.ca/apng/
http://wiki.mozilla.org/APNG_Specification
https://www.w3.org/TR/PNG/
"""

import struct
import binascii
import itertools
import io

__version__ = "0.2.1"

PNG_SIGN = b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"

# http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#C.Summary-of-standard-chunks
CHUNK_BEFORE_IDAT = {
	"cHRM", "gAMA", "iCCP", "sBIT", "sRGB", "bKGD", "hIST", "tRNS", "pHYs",
	"sPLT", "tIME", "PLTE"
}

def parse_chunks(b):
	"""Parse PNG bytes into multiple chunks. 
	
	:arg bytes b: The raw bytes of the PNG file.
	:return: A generator yielding ``(chunk_type, chunk_data)``.
	
		* ``chunk_type``: The type of the chunk.
		* ``chunk_data``: The data of the chunk, **including length, type, data, and crc**.
		
	:rtype: Iterator[tuple(str, bytes)]
	"""
	# skip signature
	i = 8
	# yield chunks
	while i < len(b):
		data_len, = struct.unpack("!I", b[i:i+4])
		type_ = b[i+4:i+8].decode("latin-1")
		yield type_, b[i:i+data_len+12]
		i += data_len + 12

def make_chunk(chunk_type, chunk_data):
	"""Create a raw chunk by composing chunk type and data. It
	calculates chunk length and CRC for you.

	:arg str chunk_type: PNG chunk type.
	:arg bytes chunk_data: PNG chunk data, **excluding chunk length, type, and CRC**.
	:rtype: bytes
	"""
	out = struct.pack("!I", len(chunk_data))
	chunk_data = chunk_type.encode("latin-1") + chunk_data
	out += chunk_data + struct.pack("!I", binascii.crc32(chunk_data) & 0xffffffff)
	return out
	
def read_file(file):
	"""Read ``file`` into ``bytes``.
	
	:arg file type: path-like or file-like
	:rtype: bytes
	"""
	if hasattr(file, "read"):
		return file.read()
	if hasattr(file, "read_bytes"):
		return file.read_bytes()
	with open(file, "rb") as f:
		return f.read()
		
def write_file(file, b):
	"""Write ``b`` to file ``file``.
	
	:arg file type: path-like or file-like object.
	:arg bytes b: The content.
	"""
	if hasattr(file, "write"):
		file.write(b)
	elif hasattr(file, "write_bytes"):
		file.write_bytes(b)
	else:
		with open(file, "wb") as f:
			f.write(b)
	
def open_file(file, mode):
	"""Open a file.

	:arg file: file-like or path-like object.
	:arg str mode: ``mode`` argument for :func:`open`.
	"""
	if hasattr(file, "read"):
		return file
	if hasattr(file, "open"):
		return file.open(mode)
	return open(file, mode)
			
def file_to_png(fp):
	"""Convert an image to PNG format with Pillow.
	
	:arg file-like fp: The image file.
	:rtype: bytes
	"""
	import PIL.Image # pylint: disable=import-error
	with io.BytesIO() as dest:
		PIL.Image.open(fp).save(dest, "PNG", optimize=True)
		return dest.getvalue()
	
class PNG:
	"""Represent a PNG image."""
	def __init__(self):
		self.hdr = None
		self.end = None
		self.width = None
		self.height = None
		self.chunks = []
		
	def init(self):
		"""Extract some info from chunks"""
		for type_, data in self.chunks:
			if type_ == "IHDR":
				self.hdr = data
			elif type_ == "IEND":
				self.end = data
				
		if self.hdr:
			# grab w, h info
			self.width, self.height = struct.unpack("!II", self.hdr[8:16])
			
	@classmethod
	def open(cls, file):
		"""Open a PNG file.
		
		:arg file: Input file.
		:type file: path-like or file-like
		:rtype: :class:`PNG`
		"""
		return cls.from_bytes(read_file(file))
		
	@classmethod
	def open_any(cls, file):
		"""Open an image file. If the image is not PNG format, it would convert
		the image into PNG with Pillow module. If the module is not
		installed, :class:`ImportError` would be raised.
		
		:arg file: Input file.
		:type file: path-like or file-like
		:rtype: :class:`PNG`
		"""
		with open_file(file, "rb") as f:
			header = f.read(8)
			f.seek(0)
			if header != PNG_SIGN:
				b = file_to_png(f)
			else:
				b = f.read()
		return cls.from_bytes(b)
		
	@classmethod
	def from_bytes(cls, b):
		"""Create :class:`PNG` from raw bytes.
		
		:arg bytes b: The raw bytes of the PNG file.
		:rtype: :class:`PNG`
		"""
		im = cls()
		im.chunks = list(parse_chunks(b))
		im.init()
		return im
		
	@classmethod
	def from_chunks(cls, chunks):
		"""Construct PNG from raw chunks.
		
		:arg chunks: A list of ``(chunk_type, chunk_raw_data)``. Also see
			:func:`chunks`.
		:type chunks: list[tuple(str, bytes)]
		"""
		im = cls()
		im.chunks = chunks
		im.init()
		return im
		
		
	def to_bytes(self):
		"""Convert the entire image to bytes.
		
		:rtype: bytes
		"""
		chunks = [PNG_SIGN]
		chunks.extend(c[1] for c in self.chunks)
		return b"".join(chunks)
		
	def save(self, file):
		"""Save the entire image to a file.

		:arg file: Output file.
		:type file: path-like or file-like
		"""
		write_file(file, self.to_bytes())
		
class FrameControl:
	"""A data class holding fcTL info."""
	def __init__(self, width=None, height=None, x_offset=0, y_offset=0,
			delay=100, delay_den=1000, depose_op=1, blend_op=0):
		"""Parameters are assigned as object members. See
		`https://wiki.mozilla.org/APNG_Specification 
		<https://wiki.mozilla.org/APNG_Specification#.60fcTL.60:_The_Frame_Control_Chunk>`_
		for the detail of fcTL.
		"""
		self.width = width
		self.height = height
		self.x_offset = x_offset
		self.y_offset = y_offset
		self.delay = delay
		self.delay_den = delay_den
		self.depose_op = depose_op
		self.blend_op = blend_op
		
	def to_bytes(self):
		"""Convert to bytes.
		
		:rtype: bytes
		"""
		return struct.pack(
			"!IIIIHHbb", self.width, self.height, self.x_offset, self.y_offset,
			self.delay, self.delay_den, self.depose_op, self.blend_op
		)
		
	@classmethod
	def from_bytes(cls, b):
		"""Contruct fcTL info from bytes.
		
		:arg bytes b: The length of ``b`` must be *28*, excluding sequence
			number and CRC.
		"""
		return cls(*struct.unpack("!IIIIHHbb", b))

class APNG:
	"""Represent an APNG image."""
	def __init__(self, num_plays=0):
		"""An :class:`APNG` is composed by multiple :class:`PNG` s and
		:class:`FrameControl`, which can be inserted with :meth:`append`.
		
		:arg int num_plays: Number of times to loop. 0 = infinite.
			
		:var frames: The frames of APNG.
		:vartype frames: list[tuple(PNG, FrameControl)]
		:var int num_plays: same as ``num_plays``.
		"""
		self.frames = []
		self.num_plays = num_plays
		
	def append(self, png, **options):
		"""Append one frame.
		
		:arg PNG png: Append a :class:`PNG` as a frame.
		:arg dict options: The options for :class:`FrameControl`.
		"""
		if not isinstance(png, PNG):
			raise TypeError("Expect an instance of `PNG` but got `{}`".format(png))
		control = FrameControl(**options)
		if control.width is None:
			control.width = png.width
		if control.height is None:
			control.height = png.height
		self.frames.append((png, control))
		
	def append_file(self, file, **options):
		"""Create a PNG from file and append the PNG as a frame.
		
		:arg file: Input file.
		:type file: path-like or file-like.
		:arg dict options: The options for :class:`FrameControl`.
		"""
		self.append(PNG.open_any(file), **options)
		
	def to_bytes(self):
		"""Convert the entire image to bytes.
		
		:rtype: bytes
		"""
		
		# grab the chunks we needs
		out = [PNG_SIGN]
		# FIXME: it's tricky to define "other_chunks". HoneyView stop the 
		# animation if it sees chunks other than fctl or idat, so we put other
		# chunks to the end of the file
		other_chunks = []
		seq = 0
		
		# for first frame
		png, control = self.frames[0]
		
		# header
		out.append(png.hdr)
		
		# acTL
		out.append(make_chunk("acTL", struct.pack("!II", len(self.frames), self.num_plays)))
		
		# fcTL
		if control:
			out.append(make_chunk("fcTL", struct.pack("!I", seq) + control.to_bytes()))
			seq += 1
		
		# and others...
		idat_chunks = []
		for type_, data in png.chunks:
			if type_ in ("IHDR", "IEND"):
				continue
			if type_ == "IDAT":
				# put at last
				idat_chunks.append(data)
				continue
			out.append(data)
		out.extend(idat_chunks)
		
		# FIXME: we should do some optimization to frames...
		# for other frames
		for png, control in self.frames[1:]:
			# fcTL
			out.append(
				make_chunk("fcTL", struct.pack("!I", seq) + control.to_bytes())
			)
			seq += 1
			
			# and others...
			for type_, data in png.chunks:
				if type_ in ("IHDR", "IEND") or type_ in CHUNK_BEFORE_IDAT:
					continue
				elif type_ == "IDAT":
					# convert IDAT to fdAT
					out.append(
						make_chunk("fdAT", struct.pack("!I", seq) + data[8:-4])
					)
					seq += 1
				else:
					other_chunks.append(data)
		
		# end
		out.extend(other_chunks)
		out.append(png.end)
		
		return b"".join(out)
		
	@classmethod
	def from_files(cls, files, **options):
		"""Create an APNG from multiple files.
		
		This is a shortcut of::
		
			im = APNG()
			for file in files:
				im.append_file(file, **options)
				
		:arg list files: A list of filename. See :meth:`PNG.open`.
		:arg dict options: Options for :class:`FrameControl`.
		:rtype: APNG
		"""
		im = cls()
		for file in files:
			im.append_file(file, **options)
		return im
		
	@classmethod
	def from_bytes(cls, b):
		"""Create an APNG from raw bytes.
		
		:arg bytes b: The raw bytes of the APNG file.
		:rtype: APNG
		"""
		hdr = None
		head_chunks = []
		end = ("IEND", make_chunk("IEND", b""))
		
		frame_chunks = []
		frames = []
		num_plays = 0
		
		control = None
		
		for type_, data in parse_chunks(b):
			if type_ == "IHDR":
				hdr = data
				frame_chunks.append((type_, data))
			elif type_ == "acTL":
				_num_frames, num_plays = struct.unpack("!II", data[8:-4])
				continue
			elif type_ == "fcTL":
				if any(type_ == "IDAT" for type_, data in frame_chunks):
					# IDAT inside chunk, go to next frame
					frame_chunks.append(end)
					frames.append((PNG.from_chunks(frame_chunks), control))
					
					control = FrameControl.from_bytes(data[12:-4])
					# https://github.com/PyCQA/pylint/issues/2072
					# pylint: disable=typecheck
					hdr = make_chunk("IHDR", struct.pack("!II", control.width, control.height) + hdr[16:-4])
					frame_chunks = [("IHDR", hdr)]
				else:
					control = FrameControl.from_bytes(data[12:-4])
			elif type_ == "IDAT":
				frame_chunks.extend(head_chunks)
				frame_chunks.append((type_, data))
			elif type_ == "fdAT":
				# convert to IDAT
				frame_chunks.extend(head_chunks)
				frame_chunks.append(("IDAT", make_chunk("IDAT", data[12:-4])))
			elif type_ == "IEND":
				# end
				frame_chunks.append(end)
				frames.append((PNG.from_chunks(frame_chunks), control))
				break
			elif type_ in CHUNK_BEFORE_IDAT:
				head_chunks.append((type_, data))
			else:
				frame_chunks.append((type_, data))
				
		o = cls()
		o.frames = frames
		o.num_plays = num_plays
		return o
		
	@classmethod
	def open(cls, file):
		"""Open an APNG file.
		
		:arg file: Input file.
		:type file: path-like or file-like.
		:rtype: APNG
		"""
		return cls.from_bytes(read_file(file))
		
	def save(self, file):
		"""Save the entire image to a file.

		:arg file: Output file.
		:type file: path-like or file-like
		"""
		write_file(file, self.to_bytes())
