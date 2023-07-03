"""
monobit.formats.mac.dfont - MacOS suitcases and resources

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import Counter
from itertools import accumulate
from io import BytesIO

from ...struct import big_endian as be
from ...magic import FileFormatError
from ...streams import Stream
from ...properties import Props, reverse_dict
from ...pack import Pack

from ..sfnt import load_sfnt, save_sfnt, MAC_ENCODING, STYLE_MAP
from .nfnt import (
    extract_nfnt, convert_nfnt,
    subset_for_nfnt, convert_to_nfnt, nfnt_data_to_bytes, generate_nfnt_header
)
from .fond import extract_fond, convert_fond, create_fond


##############################################################################
# encoding constants

# fonts which claim mac-roman encoding but aren't
NON_ROMAN_NAMES = {
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/SYMBOL.TXT
    # > The Mac OS Symbol encoding shares the script code smRoman
    # > (0) with the Mac OS Roman encoding. To determine if the Symbol
    # > encoding is being used, you must check if the font name is
    # > "Symbol".
    'Symbol': 'mac-symbol',
    'Cairo': '',
    'Taliesin': '',
    'Mobile': '',
    'Zapf Dingbats': '',
}


# Apple IIgs Technote #41, Font Family Numbers
_FONT_NAMES = {
    # 0: 'System Font',
    # 1: 'System Font',
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
    13: 'Zapf Dingbats',
    14: 'Bookman',
    15: 'Helvetica Narrow',
    16: 'Palatino',
    18: 'Zapf Chancery',
    20: 'Times',
    21: 'Helvetica',
    22: 'Courier',
    23: 'Symbol',
    24: 'Taliesin',
    33: 'Avant Garde',
    34: 'New Century Schoolbook',
    65533: 'Chicago',
    65534: 'Shaston',
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


def parse_resource_fork(data, formatstr=''):
    """Parse a bare resource and convert to fonts."""
    resource_table = _extract_resource_fork_header(data)
    rsrc = _extract_resources(data, resource_table)
    logging.debug(rsrc)
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
                    name=name, **extract_fond(data, offset)
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
                rsrc_type, rsrc_id, extract_nfnt(data, offset)
            ))
        elif rsrc_type == b'sfnt':
            logging.debug(
                'TrueType font resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
            bytesio = Stream.from_data(data[offset:], mode='r')
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
            props = convert_fond(**kwargs)
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
                'source_format': f'[Mac] {format}',
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
                    'point_size': font_size,
                    'family': _FONT_NAMES.get(font_number, str(font_number))
                })
                # prefer directory info to info inferred from resource ID
                # (in so far provided by FOND or directory FONT)
                props.update(info.get(rsrc_id, info.get(font_number, {})))
            else:
                # update properties with directory info
                props.update(info.get(rsrc_id, {}))
            if 'encoding' not in props or props.get('family', '') in NON_ROMAN_NAMES:
                props['encoding'] = NON_ROMAN_NAMES.get(props.get('family', ''), 'mac-roman')
            font = convert_nfnt(props, **kwargs)
            if font.glyphs:
                font = font.label()
                fonts.append(font)
    return fonts


###############################################################################
# dfont writer

# from FontForge notes https://fontforge.org/docs/techref/macformats.html :
# > When an ‘sfnt’ resource contains a font with a multibyte encoding (CJK or
# > unicode) then the ‘FOND’ does not have entries for all the characters. The
# > ‘sfnt’ will (always?) have a MacRoman encoding as well as the multibyte encoding
# > and the ‘FOND’ will contain information on just that subset of the font. (I have
# > determined this empirically, I have seen no documentation on the subject)
#
# > Currently bitmap fonts for multibyte encodings are stored inside an sfnt
# > (truetype) resource in the ‘bloc’ and ‘bdat’ tables. When this happens there are
# > a series of dummy ‘NFNT’ resources in the resource file, one for each strike.
# > Each resource is 26 bytes long (which means they contain the FontRec structure
# > but no data tables) and are flagged by having rowWords set to 0. (I have
# > determined this empirically, I have seen no documentation on the subject)


def save_dfont(fonts, outstream, resource_type):
    """
    Save font to MacOS resource fork or data-fork resource.

    resource_type: type of resource to store font in. One of `sfnt`, `NFNT`.
    """
    resource_type = resource_type.lower()
    if resource_type not in ('sfnt', 'nfnt'):
        raise ValueError(
            'Only saving to sfnt or NFNT resource currently supported'
        )
    resources = []
    if resource_type == 'sfnt':
        sfnt_io = BytesIO()
        result = save_sfnt(fonts, sfnt_io)
        font, *_ = fonts
        family_id = _get_family_id(font.family, font.encoding)
        resources.append(
            Props(type=b'sfnt', id=family_id, name='', data=sfnt_io.getvalue()),
        )
    # reduce fonts to what's storable in (stub) FOND/NFNT
    # we need a Pack for _group_families
    fonts = Pack(subset_for_nfnt(_f) for _f in fonts)
    for family_id, style_group in _group_families(fonts):
        i = 0
        for style_id, size_group in style_group:
            for font in size_group:
                if resource_type == 'sfnt':
                    # create stub NFNT if the bitmaps are in an sfnt
                    nfnt_data = generate_nfnt_header(font, endian='big')
                else:
                    nfnt_data = convert_to_nfnt(
                        font, endian='big', ndescent_is_high=True,
                        create_width_table=True, create_height_table=False,
                    )
                resources.append(
                    Props(
                        type=b'NFNT',
                        # note that we calculate this *separately* in the FOND builder
                        id=family_id + i,
                        # are there any specifications for the name?
                        name=font.name,
                        data=nfnt_data_to_bytes(nfnt_data),
                    ),
                )
                i += 1
        fond_data = create_fond(style_group, family_id)
        resources.append(
            Props(
                type=b'FOND', id=family_id,
                name=font.family, data=fond_data,
            ),
        )
    _write_resource_fork(outstream, resources)


def _get_family_id(name, encoding):
    """Generate a resource id based on the font's properties."""
    script_code = reverse_dict(MAC_ENCODING).get(encoding, 0)
    return _hash_to_id(name, script=script_code)


def _write_resource_fork(outstream, resources):
    """
    Write a Mac dfont/resource fork.

    resources: list of ns(type, id, name, data)
    """
    # order resources by type (so all resources of the same type are consecutive
    resources.sort(key=lambda _res: _res.type)
    # counter follows insertion order
    types = Counter(_res.type for _res in resources)
    # construct the resource map
    map_header = _MAP_HEADER(
        # not sure what these are
        attributes=0,
        # type list comes straight after this header
        # -2 because the last_type in this header definition
        # is counted as part of the type list
        type_list_offset=_MAP_HEADER.size-2, #28,
        # after type list plus reference lists
        name_list_offset=(
            _MAP_HEADER.size
            + _TYPE_ENTRY.size * len(types)
            + _REF_ENTRY.size * len(resources)
        ),
        # number of types minus 1
        last_type=len(types) - 1,
    )
    # construct the type list
    type_list = [
        _TYPE_ENTRY(
            rsrc_type=_type,
            last_rsrc=_count - 1,
            # ref_list_offset='uint16',
        )
        for _type, _count in types.items()
    ]
    offset = 2 + _TYPE_ENTRY.size * len(type_list)
    for entry in type_list:
        entry.ref_list_offset = offset
        offset += _REF_ENTRY.size * (entry.last_rsrc + 1)
    type_list = (_TYPE_ENTRY * len(types))(*type_list)
    # construct the name list
    name_list = tuple(
        bytes((len(_res.name),)) + _res.name.encode('mac-roman')
        for _res in resources
    )
    name_offsets = accumulate((len(_n) for _n in name_list), initial=0)
    data_offsets = accumulate(
        # include 4 bytes for length field
        (4 + len(_res.data) for _res in resources),
        initial=0
    )
    # construct the reference list
    reference_list = (
        _REF_ENTRY(
            rsrc_id=_res.id,
            name_offset=-1 if not _res.name else _name_offset,
            attributes=0,
            # we need a 3-byte offset, will have to construct ourselves...
            data_offset_hi=_data_offset // 0x1000,
            data_offset=_data_offset % 0x1000,
        )
        for _res, _name_offset, _data_offset in zip(resources, name_offsets, data_offsets)
    )
    reference_list = (_REF_ENTRY * len(resources))(*reference_list)
    rsrc_map = (
        bytes(map_header)
        + bytes(type_list)
        + bytes(reference_list)
        + b''.join(name_list)
    )
    data = b''.join(
        bytes(be.uint32(len(_res.data))) + _res.data
        for _res in resources
    )
    rsrc_header = _RSRC_HEADER(
        # data come right after the header and padding
        data_offset=256,
        map_offset=256 + len(data),
        data_length=len(data),
        map_length=len(rsrc_map),
    )
    outstream.write(
        bytes(rsrc_header)
        + data
        + rsrc_map
    )


# family name hash algorithm
# ported from https://github.com/zoltan-dulac/fondu/blob/master/ufond.c
#
# FONDU licence:
# > PfaEdit is copyright (C) 2000,2001,2002,2003 by George Williams
# >
# >    Redistribution and use in source and binary forms, with or without
# >    modification, are permitted provided that the following conditions are met:
# >
# >    Redistributions of source code must retain the above copyright notice, this
# >    list of conditions and the following disclaimer.
# >
# >    Redistributions in binary form must reproduce the above copyright notice,
# >    this list of conditions and the following disclaimer in the documentation
# >    and/or other materials provided with the distribution.
# >
# >    The name of the author may not be used to endorse or promote products
# >    derived from this software without specific prior written permission.
# >
# >    THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
# >    WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# >    MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# >    EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# >    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# >    PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# >    OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# >    WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# >    OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# >    ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# >
# > The configure script is subject to the GNU public license. See the file
# > COPYING.

def _hash_to_id(family_name, script):
    """Generate a resource id based on the font family name."""
    low = 128
    high = 0x4000
    hash = 0
    if script:
        low = 0x4000 + (script-1)*0x200;
        high = low + 0x200;
    for ch in family_name:
        temp = (hash>>28) & 0xf
        hash = (hash<<4) | temp
        hash ^= ord(ch) - 0x20
    hash %= (high-low)
    hash += low
    return hash


def mac_style_from_name(style_name):
    """Get font style from human-readable representation."""
    return sum((2<<_bit for _bit, _k in STYLE_MAP.items() if _k in style_name))


def _group_families(fonts):
    """Group pack of fonts by families and subfamilies."""
    families = tuple(sorted(
        # assuming encoding stays the same across family
        (_get_family_id(_name, _group[0].encoding), _group)
        for _name, _group in fonts.itergroups('family')
    ))
    fond_families = []
    for id, group in families:
        chars = set(_font.get_codepoints() for _font in group)
        if len(set(chars)) > 1:
            logging.warning(
                "Can't combine fonts into families: different character ranges."
            )
            return _group_individually(fonts)
        spacings = set(_font.spacing for _font in group)
        if len(set(spacings)) > 1:
            logging.warning(
                "Can't combine fonts into families: different spacing characteristics."
            )
            return _group_individually(fonts)
        style_groups = tuple(sorted(
            (mac_style_from_name(_subfamily), _fonts)
            for _subfamily, _fonts in group.itergroups('subfamily')
        ))
        for _, group in style_groups:
            sizes = tuple(_f.point_size for _f in group)
            if len(sizes) != len(set(sizes)):
                logging.warning(
                    "Can't combine fonts into families: duplicate style and size."
                )
            return _group_individually(fonts)
        fond_families.append((id, style_groups))
    return fond_families


def _group_individually(fonts):
    """Return each individual font as its own family."""
    fond_families = tuple(sorted(
        (
            # we're assuming names differ
            _get_family_id(_font.name, _font.encoding),
            ((mac_style_from_name(_font.subfamily), [_font]),)
        )
        for _font in fonts
    ))
    return fond_families
