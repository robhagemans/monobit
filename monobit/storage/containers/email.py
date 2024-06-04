"""
monobit.storage.containers.email - files embedded in email messages

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT

Based on Python documentation examples at
https://docs.python.org/3/library/email.examples.html

> Thanks to Matthew Dixon Cowles for the original inspiration and examples.

> © Copyright 2001-2024, Python Software Foundation.
> This page is licensed under the Python Software Foundation License Version 2.
> Examples, recipes, and other code in the documentation are additionally
> licensed under the Zero Clause BSD License.
> See https://docs.python.org/license.html for more information.
"""

import email
from email.message import EmailMessage
from email.policy import SMTP, default
import mimetypes
from pathlib import Path
from io import BytesIO

from ..streams import Stream, KeepOpen
from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import Archive


###############################################################################

@containers.register(
    name='email',
    patterns=('*.eml', '*.msg'),
)
class EmailContainer(Archive):

    def __init__(
            self, stream, mode='r',
            sender:str='me@here',
            recipient:str='you@there',
            subject:str='Files',
        ):
        """
        files in email attachments.

        sender: email From field
        recipient: email To field
        subject: email Subject
        """
        cls = type(self)
        # write
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self._wrapped_stream = stream
        self._files = []
        self._data = {}
        super().__init__(mode)

    def close(self):
        """Close the archive, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            message = _write(
                self.subject, self.sender, self.recipient, self._files
            )
            self._wrapped_stream.write(message)
            for file in self._files:
                file.close()
        self._wrapped_stream.close()
        super().close()

    def is_dir(self, name):
        """Item at `name` is a directory."""
        return Path(name) == Path('.')

    def list(self):
        self._get_names_and_data()
        return self._data.keys()

    def open(self, name, mode):
        """Open a binary stream in the container."""
        if mode == 'r':
            return self._open_read(name)
        else:
            return self._open_write(name)

    def _open_read(self, name):
        """Open input stream on source wrapper."""
        infile = self._wrapped_stream
        self._get_names_and_data()
        name = str(name)
        try:
            data = self._data[name]
        except KeyError:
            raise FileNotFoundError(f"No attachment '{name}' found.")
        return Stream.from_data(data, mode='r', name=name)

    def _get_names_and_data(self):
        """Find all identifiers with payload."""
        if self._data:
            return
        if self.mode == 'w':
            return
        self._data = _read(self._wrapped_stream)

    def _open_write(self, name):
        """Open output stream on source wrapper."""
        newfile = Stream(KeepOpen(BytesIO()), mode='w', name=name)
        if name in self._files:
            logging.warning('Creating multiple files of the same name `%s`.', name)
        self._files.append(newfile)
        return newfile

def _write(subject, sender, recipient, files):
    # Create the message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['To'] = recipient
    msg['From'] = sender
    msg.preamble = 'This is a multi-part message in MIME format.\n'
    for file in files:
        filename = str(file.name)
        # Guess the content type based on the file's extension.  Encoding
        # will be ignored, although we should check for simple things like
        # gzip'd or compressed files.
        ctype, encoding = mimetypes.guess_type(filename)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed), so
            # use a generic bag-of-bits type.
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        file.seek(0)
        data = file.read()
        msg.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=filename
        )
    # Now send or store the message
    return msg.as_bytes(policy=SMTP)

def _read(instream):
    msg = email.message_from_binary_file(instream, policy=default)
    data = {}
    counter = 1
    for part in msg.walk():
        # multipart/* are just containers
        if part.get_content_maintype() == 'multipart':
            continue
        # Applications should really sanitize the given filename so that an
        # email message can't be used to overwrite important files
        filename = part.get_filename()
        if not filename:
            ext = mimetypes.guess_extension(part.get_content_type())
            if not ext:
                # Use a generic bag-of-bits extension
                ext = '.bin'
            filename = f'part-{counter:03d}{ext}'
        counter += 1
        data[filename] = part.get_payload(decode=True)
    return data
