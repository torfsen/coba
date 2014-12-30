#!/usr/bin/env python

"""
Disk-based blob store.
"""

import collections
import cStringIO
import errno
import gzip
import hashlib
import os
import os.path
import shutil
import tempfile


def _hash_and_compress(in_file, out_file, hasher=hashlib.sha1, block_size=2**20):
    """
    Compress a file and compute its hash on the fly.

    Reads content from ``in_file`` in chunks of ``block_size`` bytes.
    The content is compressed and hashed on the fly. The compressed
    output is stored in ``out_file`` and the hex digest of the hash is
    returned.
    """
    h = hasher()
    with gzip.GzipFile(filename='', fileobj=out_file) as gzip_file:
        while True:
            block = in_file.read(block_size)
            if not block:
                break
            h.update(block)
            gzip_file.write(block)
    return h.hexdigest()


_undefined = object()


class BlobStore(collections.Mapping):
    """
    A blob store.

    This blob store allows you to store arbitrary data on disk. Entries
    are identified by their hash, which is computed when data is stored
    and can then be used to retrieve the data at a later point.
    """

    @classmethod
    def create(cls, path):
        """
        Create a new blob store.

        This creates the necessary directory structure in the given
        directory. The directory must not exist already.

        Returns an instance of ``BlobStore``.
        """
        if os.path.isdir(path):
            raise ValueError('The directory "%s" already exists.' % path)
        os.mkdir(path)
        for d in ['blobs', 'tmp']:
            os.mkdir(os.path.join(path, d))
        return cls(path)

    def __init__(self, path):
        """
        Access an existing blob store.

        ``path`` is the path to an existing blob store directory as
        created using ``create``.
        """
        if not os.path.isdir(path):
            raise ValueError('The directory "%s" does not exist.' % path)
        self.path = path
        self._blob_dir = os.path.join(path, 'blobs')
        if not os.path.isdir(self._blob_dir):
            raise ValueError('The directory "%s" is not a valid blob store.' %
                             path)
        self._temp_dir = os.path.join(path, 'tmp')

    def _split_hash(self, h):
        """
        Split a hash into directory and filename parts.
        """
        return h[:2], h[2:]

    def put(self, data):
        """
        Store content in the blob store.

        ``data`` can either be a string or an open file-like object.
        Its content is stored in the blob store in compressed form and
        the content's hash is returned. The hash can later be used to
        retrieve the data from the blob store.
        """
        if not hasattr(data, 'read'):
            # Not a file, assume string
            data = cStringIO.StringIO(data)
        # We want to use the data's hash for constructing the output
        # filename. However, the hash is only available after the data
        # has been compressed (to avoid going over the data twice).
        # Therefore we compress the data to a temporary file and move
        # it upon completion. Since the temporary file resides inside
        # the blob store directory (and hence on the same filesystem)
        # moving the file should be very efficient.
        temp_file = tempfile.NamedTemporaryFile(dir=self._temp_dir,
                                                delete=False)
        try:
            hashsum = _hash_and_compress(data, temp_file)
            dirname, filename = self._split_hash(hashsum)
            dirpath = os.path.join(self._blob_dir, dirname)
            if not os.path.isdir(dirpath):
                os.mkdir(dirpath)
            os.rename(temp_file.name, os.path.join(dirpath, filename))
        finally:
            try:
                os.unlink(temp_file.name)
            except:
                pass
        return hashsum

    def get(self, hashsum, default=_undefined):
        """
        Retrieve data from the blob store.

        Returns data that was previously stored via ``put``.
        ``hashsum`` is the data's hash as returned by ``put``.

        If there is no data stored for the given hash then ``KeyError``
        is raised, unless ``default`` is set in which case that value
        is returned instead.

        ``bs.get(h)`` is equivalent to ``bs[h]``.
        """
        dirname, filename = self._split_hash(hashsum)
        try:
            with gzip.open(os.path.join(self._blob_dir, dirname,
                           filename)) as f:
                return f.read()
        except IOError as e:
            if e.errno == errno.ENOENT:
                if default is _undefined:
                    raise KeyError('No blob for hashsum "%s".' % hashsum)
                return default
            raise

    def __getitem__(self, hashsum):
        return self.get(hashsum)

    def __delitem__(self, hashsum):
        return self.remove(hashsum)

    def __setitem__(self, key, value):
        raise TypeError('Indexed writing is not possible. Use "put".')

    def __iter__(self):
        for root, dirnames, filenames in os.walk(self._blob_dir):
            base = os.path.basename(root)
            for filename in filenames:
                yield base + filename

    def __len__(self):
        file_count = 0
        for root, dirnames, filenames in os.walk(self._blob_dir):
            file_count += len(filenames)
        return file_count

    def clear(self):
        """
        Remove all entries.
        """
        shutil.rmtree(self._blob_dir)
        os.mkdir(self._blob_dir)

    def remove(self, hashsum):
        """
        Remove an entry.

        Removes the entry with the given hash. ``bs.remove(h)`` is
        equivalent to ``del bs[h]``.
        """
        dirname, filename = self._split_hash(hashsum)
        try:
            os.unlink(os.path.join(self._blob_dir, dirname, filename))
        except IOError as e:
            if e.errno == errno.ENOENT:
                raise KeyError('No blob for hashsum "%s".' % hashsum)
            raise
