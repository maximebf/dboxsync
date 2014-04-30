import os
import threading
import datetime
import time
import shutil
import Queue
import logging


logger = logging.getLogger(__name__)
CURSOR_FILENAME = ".dboxsync_cursor"


class DropboxObject(object):
    def __init__(self, dropbox_client, path, local_path=None, delta_cursor=None):
        self.dropbox = dropbox_client
        self.path = '/' + path.strip('/')
        self.local_path = local_path
        self.delta_cursor = delta_cursor
        self._metadata = None
        self.change_callback = None

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = self.dropbox.metadata(self.path)
        return self._metadata

    def is_dir(self):
        return self.metadata['is_dir']

    def download(self):
        self._metadata = None
        return self._download(self.metadata, self.local_path)

    def _download(self, meta, dest):
        if meta['is_dir']:
            return self._download_dir(meta, dest)
        return self._download_file(meta, dest)

    def _download_dir(self, meta, dest):
        if not os.path.exists(dest):
            logger.info("Creating directory '%s'" % dest)
            os.mkdir(dest)

        contents = meta['contents'] if 'contents' in meta else []
        current_entries = []
        for item in contents:
            item_dest = os.path.join(dest, os.path.basename(item['path']))
            current_entries.append(os.path.basename(item['path']))
            self._download(item, item_dest)

    def _download_file(self, meta, dest):
        if os.path.exists(dest) and os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(meta['path']))
        logger.info("Downloading '%s' to '%s'" % (meta['path'], dest))
        out = open(dest, 'wb')
        try:
            with self.dropbox.get_file(meta['path']) as f:
                out.write(f.read())
        except:
            out.close()
            os.remove(dest)
            logger.error("Failed downloading '%s'" % meta['path'])
        else:
            out.close()

    def delta(self, cursor=None, save_cursor=False):
        if cursor is None:
            cursor = self.delta_cursor
        has_more = True
        entries = []
        new_cursor = None
        logger.debug("Checking changes of '%s' (from cursor: %s)" % (self.path, ('no' if cursor is None else 'yes')))
        while has_more:
            meta = self.dropbox.delta(cursor=cursor, path_prefix=self.path.lower())
            entries.extend(meta['entries'])
            if new_cursor is None:
                new_cursor = meta['cursor']
            has_more = meta['has_more']
        if save_cursor:
            self.delta_cursor = new_cursor
        return (entries, new_cursor)

    def has_changed(self, cursor=None):
        return len(self.delta(cursor)[0]) > 0

    def sync(self, cursor=None):
        if cursor is None:
            cursor = self.delta_cursor
        entries, new_cursor = self.delta(cursor, save_cursor=True)
        self.sync_entries(entries)
        return new_cursor

    def sync_entries(self, entries, cursor=None):
        for (path, meta) in entries:
            dest = self._make_path_local(path)
            if meta is None:
                logger.info("Removing '%s'" % dest)
                if os.path.exists(dest):
                    if os.path.isdir(dest):
                        shutil.rmtree(dest)
                    else:
                        os.remove(dest)
            else:
                self._download(meta, dest)

        if cursor is not None:
            self.delta_cursor = cursor

        if self.change_callback is not None:
            self.change_callback(entries)

    def _make_path_local(self, path):
        return os.path.join(self.local_path, path[len(self.path) + 1:]).rstrip('/')

    def create_threaded_sync(self):
        return Watcher.watch(self, self.sync_entries())

    def upload(self):
        return self._upload(self.local_path, self.path)

    def _upload(self, src, dest):
        if os.path.isdir(src):
            return self._upload_dir(src, dest)
        return self._upload_file(src, dest)

    def _upload_dir(self, src, dest):
        self.dropbox.file_create_folder(dest)
        for f in os.listdir(src):
            self._upload(os.path.join(src, f), os.path.join(dest, f))

    def _upload_file(self, src, dest):
        with open(src, 'rb') as f:
            resp = self.dropbox.put_file(dest, f)
        return resp


class CursorFile(object):
    def __init__(self, path):
        self.path = path
        self._filename = None
        self.value = None

    def read(self):
        if self.filename is None or not os.path.exists(self.filename):
            return None
        with open(self.filename, 'r') as f:
            self.value = f.read()
        return self.value

    def __str__(self):
        if self.value is None:
            self.read()
        return self.value

    def write(self, dbobject):
        if dbobject.delta_cursor is not None:
            with open(self.filename, 'w') as f:
                f.write(dbobject.delta_cursor)

    @property
    def filename(self):
        if self._filename is None:
            if not os.path.exists(self.path):
                self._filename = None
            elif os.path.isdir(self.path):
                self._filename = os.path.join(self.path, CURSOR_FILENAME)
            else:
                self._filename = os.path.join(os.path.dirname(self.path), "." + os.path.basename(self.path) + CURSOR_FILENAME)
        return self._filename

    
class Thread(threading.Thread):
    def __init__(self):
        super(Thread, self).__init__()
        self.running = False

    def start(self):
        self.running = True
        super(Thread, self).start()

    def stop(self):
        self.running = False


class Watcher(Thread):
    def __init__(self, wait_time=10):
        super(Watcher, self).__init__()
        self.handlers = []
        self.wait_time = wait_time

    @classmethod
    def watch(cls, dbobject, callback):
        w = cls()
        w.register(dbobject, callback)
        return w

    def register(self, dbobject, callback, ignore_first_call=False):
        self.handlers.append([dbobject, callback, None, ignore_first_call])

    def run(self):
        logger.debug('[Thread %s] Starting watcher' % self.ident)
        first_call = True
        while self.running:
            for i in xrange(0, len(self.handlers)):
                dbobject, callback, cursor, ignore_first_call = self.handlers[i]
                entries, cursor = dbobject.delta(cursor=cursor)
                if not (ignore_first_call and first_call) and len(entries) > 0:
                    logger.info("[Thread %s] Detected changes in '%s'" % (self.ident, dbobject.path))
                    callback(entries, cursor)
                self.handlers[i][2] = cursor
            first_call = False
            time.sleep(self.wait_time)


class QueueingWatcher(Watcher):
    @classmethod
    def watch(cls, dbobject):
        w = cls()
        return (w, w.register(dbobject))

    def register(self, dbobject, queue=None, ignore_first_call=False):
        queue = Queue.Queue() if queue is None else queue
        def callback(entries, cursor):
            queue.put((entries, cursor))
        super(QueueingWatcher, self).register(dbobject, callback, ignore_first_call)
        return queue


class QueueListener(Thread):
    def __init__(self, queue, callback=None):
        super(QueueListener, self).__init__()
        self.callbacks = []
        self.queue = queue
        if callback is not None:
            self.register(callback)

    def register(self, callback):
        self.callbacks.append(callback)

    def dispatch(self, *args, **kwargs):
        for callback in self.callbacks:
            callback(*args, **kwargs)

    def run(self):
        logger.debug("[Thread %s] Starting queue listener" % self.ident)
        while self.running:
            data = self.queue.get()
            logger.debug("[Thread %s] Dispatching queue message" % self.ident)
            self.dispatch(*data)
            queue.task_done()


class MultiQueueListener(Thread):
    def __init__(self):
        super(MultiQueueListener, self).__init__()
        self.handlers = []

    def register(self, queue, callbacks):
        self.handlers.append((queue, callbacks))

    def run(self):
        logger.debug("[Thread %s] Starting multi queue listener" % self.ident)
        while self.running:
            for (queue, callbacks) in self.handlers:
                try:
                    data = queue.get(False)
                    logger.debug("[Thread %s] Dispatching queue message" % self.ident)
                    for callback in callbacks:
                        callback(*data)
                except Queue.Empty:
                    pass


def scoped_callback(path_prefix, callback):
    path_prefix = '/' + path_prefix.strip('/').lower()
    def db(entries, cursor):
        scoped_entries = []
        for (path, meta) in entries:
            if path.lower().startswith(path_prefix):
                scoped_entries.append((path, meta))
        if len(scoped_entries) > 0:
            callback(scoped_entries, cursor)
    return db


class PathOptimizedCallbacks(object):
    def __init__(self):
        self.paths = {}

    def append(self, dbobject, callback):
        self.paths[dbobject.path.lower()] = (dbobject, callback)

    def optimize(self):
        paths = {}
        for path, data in self.paths.iteritems():
            matched = False
            for p in paths.keys():
                if path.startswith(p):
                    paths[p].append(data)
                    matched = True
                elif p.startswith(path):
                    paths[path] = [data]
                    paths[path].extend(paths[p])
                    del paths[p]
                    matched = True
            if not matched:
                paths[path] = [data]

        for path, items in paths.iteritems():
            dbobject = items[0][0]
            callbacks = [scoped_callback(item[0].path, item[1]) for item in items]
            yield (dbobject, callbacks)
