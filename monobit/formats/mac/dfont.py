"""
monobit.formats.mac - MacOS suitcases and resources

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging

from ...struct import big_endian as be
from ...streams import FileFormatError

from ..sfnt import load_sfnt
from .nfnt import _extract_nfnt, _convert_nfnt
from .fond import _extract_fond, _convert_fond



##############################################################################
# encoding constants

# fonts which claim mac-roman encoding but aren't
_NON_ROMAN_NAMES = {
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/SYMBOL.TXT
    # > The Mac OS Symbol encoding shares the script code smRoman
    # > (0) with the Mac OS Roman encoding. To determine if the Symbol
    # > encoding is being used, you must check if the font name is
    # > "Symbol".
    'Symbol': 'mac-symbol',
    'Cairo': '',
    'Taliesin': '',
    'Mobile': '',
}


# font names for system fonts in FONT resources
_FONT_NAMES = {
    0: 'Chicago', # system font
    1: 'application font',
    2: 'New York',
    3: 'Geneva',
    4: 'Monaco',
    5: 'Venice',
    6: 'London',
    7: 'Athens',
    8: 'San Francisco',
    9: 'Toronto',
    11: 'Cairo',
    12: 'Los Angeles',
    16: 'Palatino', # found experimentally
    20: 'Times',
    21: 'Helvetica',
    22: 'Courier',
    23: 'Symbol',
    24: 'Taliesin', # later named Mobile, but it has a FOND entry then.
}


##############################################################################
# resource fork/dfont format
# see https://developer.apple.com/library/archive/documentation/mac/pdf/MoreMacintoshToolbox.pdf

# Page 1-122 Figure 1-12 Format of a resource header in a resource fork
_RSRC_HEADER = be.Struct(
    data_offset='uint32',
    map_offset='uint32',
    data_length='uint32',
    map_length='uint32',
    # header is padded with zeros to 256 bytes
    # https://github.com/fontforge/fontforge/blob/master/fontforge/macbinary.c
    reserved='240s',
)

# Figure 1-13 Format of resource data for a single resource
_DATA_HEADER = be.Struct(
    length='uint32',
    # followed by `length` bytes of data
)

# Figure 1-14 Format of the resource map in a resource fork
_MAP_HEADER = be.Struct(
    reserved_header='16s',
    reserved_handle='4s',
    reserved_fileref='2s',
    attributes='uint16',
    type_list_offset='uint16',
    name_list_offset='uint16',
    # number of types minus 1
    last_type='uint16',
    # followed by:
    # type list
    # reference lists
    # name list
)
# Figure 1-15 Format of an item in a resource type list
_TYPE_ENTRY = be.Struct(
    rsrc_type='4s',
    # number of resources minus 1
    last_rsrc='uint16',
    ref_list_offset='uint16',
)

# Figure 1-16 Format of an entry in the reference list for a resource type
_REF_ENTRY = be.Struct(
    rsrc_id='uint16',
    name_offset='uint16',
    attributes='uint8',
    # we need a 3-byte offset, will have to construct ourselves...
    data_offset_hi='uint8',
    data_offset='uint16',
    reserved_handle='4s',
)

# Figure 1-17 Format of an item in a resource name list
# 1-byte length followed by bytes


def _parse_mac_resource(data, formatstr=''):
    """Parse a bare resource and convert to fonts."""
    resource_table = _extract_resource_fork_header(data)
    rsrc = _extract_resources(data, resource_table)
    directory = _construct_directory(rsrc)
    fonts = _convert_mac_font(rsrc, directory, formatstr)
    return fonts


def _extract_resource_fork_header(data):
    """Read a Classic MacOS resource fork header."""
    rsrc_header = _RSRC_HEADER.from_bytes(data)
    map_header = _MAP_HEADER.from_bytes(data, rsrc_header.map_offset)
    type_array = _TYPE_ENTRY.array(map_header.last_type + 1)
    # +2 because the length field is considered part of the type list
    type_list_offset = rsrc_header.map_offset + map_header.type_list_offset + 2
    type_list = type_array.from_bytes(data, type_list_offset)
    resources = []
    for type_entry in type_list:
        ref_array = _REF_ENTRY.array(type_entry.last_rsrc + 1)
        ref_list = ref_array.from_bytes(
            data, type_list_offset -2 + type_entry.ref_list_offset
        )
        for ref_entry in ref_list:
            # get name from name list
            if ref_entry.name_offset == 0xffff:
                name = ''
            else:
                name_offset = (
                    rsrc_header.map_offset + map_header.name_list_offset
                    + ref_entry.name_offset
                )
                name_length = data[name_offset]
                # should be ascii, but use mac-roman just in case
                name = data[name_offset+1:name_offset+name_length+1].decode('mac-roman')
            # construct the 3-byte integer
            data_offset = ref_entry.data_offset_hi * 0x10000 + ref_entry.data_offset
            offset = rsrc_header.data_offset + _DATA_HEADER.size + data_offset
            resources.append((type_entry.rsrc_type, ref_entry.rsrc_id, offset, name))
    return resources


def _extract_resources(data, resources):
    """Extract resources."""
    parsed_rsrc = []
    for rsrc_type, rsrc_id, offset, name in resources:
        if rsrc_type == b'FOND':
            logging.debug(
                'Font family resource #%d: type FOND name `%s`', rsrc_id, name
            )
            parsed_rsrc.append((
                rsrc_type, rsrc_id, dict(
                    name=name, **_extract_fond(data, offset)
                )
            ))
        elif rsrc_type == b'FONT' and name and not (rsrc_id % 128):
            # rsrc_id % 128 is the point size
            logging.debug(
                'Name entry #%d: type FONT name `%s`',
                rsrc_id, name
            )
            # inside macintosh:
            # > Since 0 is not a valid font size, the resource ID having
            # > 0 in the size field is used to provide only the name of
            # > the font: The name of the resource is the font name. For
            # > example, for a font named Griffin and numbered 200, the
            # > resource naming the font would have a resource ID of 25600
            # > and the resource name 'Griffin'. Size 10 of that font would
            # > be stored in a resource numbered 25610.
            # keep the name in the directory table
            parsed_rsrc.append((
                b'', rsrc_id, dict(name=name),
            ))
        elif rsrc_type in (b'NFNT', b'FONT'):
            logging.debug(
                'Bitmapped font resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
            parsed_rsrc.append((
                rsrc_type, rsrc_id, _extract_nfnt(data, offset)
            ))
        elif rsrc_type == b'sfnt':
            logging.debug(
                'TrueType font resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
            bytesio = io.BytesIO(data[offset:])
            fonts = load_sfnt(bytesio)
            parsed_rsrc.append((
                rsrc_type, rsrc_id, dict(fonts=fonts)
            ))
        else:
            logging.debug(
                'Skipped resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
    return parsed_rsrc


def _construct_directory(parsed_rsrc):
    """Construct font family directory."""
    info = {}
    for rsrc_type, rsrc_id, kwargs in parsed_rsrc:
        # new-style directory entries
        if rsrc_type == b'FOND':
            props = _convert_fond(**kwargs)
            info.update(props)
        # old-style name-only FONT resources (font_size 0)
        elif rsrc_type == b'':
            font_number = rsrc_id // 128
            info[font_number] = {'family': kwargs['name']}
    return info


def _convert_mac_font(parsed_rsrc, info, formatstr):
    """convert properties and glyphs."""
    fonts = []
    for rsrc_type, rsrc_id, kwargs in parsed_rsrc:
        if rsrc_type == b'sfnt':
            rsrc_fonts = kwargs['fonts']
            rsrc_fonts = (
                _font.modify(
                    source_format = f'[Mac] {_font.source_format}',
                )
                for _font in rsrc_fonts
            )
            fonts.extend(rsrc_fonts)
        elif rsrc_type in (b'FONT', b'NFNT'):
            format = ''.join((
                rsrc_type.decode('mac-roman'),
                f' in {formatstr}' if formatstr else ''
            ))
            props = {
                'family': kwargs.get('name', '') or f'{rsrc_id}',
                'source-format': f'[Mac] {format}',
            }
            if rsrc_type == b'FONT':
                # get name and size info from resource ID
                # https://developer.apple.com/library/archive/documentation/mac/Text/Text-191.html#HEADING191-0
                # > The resource ID of the font must equal the number produced by
                # > concatenating the font ID times 128 with the font size.
                # > Remember that fonts stored in 'FONT' resources are restricted
                # > to a point size of less than 128 and to a font ID in the range
                # > 0 to 255. The resource ID is computed by the following formula:
                # >     resourceID := (font ID * 128) + font size;
                font_number, font_size = divmod(rsrc_id, 128)
                # we've already filtered out the case font_size == 0
                props.update({
                    'point-size': font_size,
                    'family': _FONT_NAMES.get(font_number, str(font_number))
                })
                # prefer directory info to info inferred from resource ID
                # (in so far provided by FOND or directory FONT)
                props.update(info.get(rsrc_id, info.get(font_number, {})))
            else:
                # update properties with directory info
                props.update(info.get(rsrc_id, {}))
            if 'encoding' not in props or props.get('family', '') in _NON_ROMAN_NAMES:
                props['encoding'] = _NON_ROMAN_NAMES.get(props.get('family', ''), 'mac-roman')
            font = _convert_nfnt(props, **kwargs)
            if font.glyphs:
                font = font.label()
                fonts.append(font)
    return fonts
