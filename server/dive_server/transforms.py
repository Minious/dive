import os
import shutil
import tempfile

from girder_worker_utils.transforms.girder_io import GirderClientTransform


class GetPathFromItemId(GirderClientTransform):
    """
    This transform downloads a Girder Item to a directory on the local machine
    and passes its local path into the function.
    :param _id: The ID of the item to download.
    :type _id: str
    """

    def __init__(self, _id, **kwargs):
        super(GetPathFromItemId, self).__init__(**kwargs)
        self.item_id = _id

    def _repr_model_(self):
        return "{}('{}')".format(self.__class__.__name__, self.item_id)

    def transform(self):
        temp_dir = tempfile.mkdtemp()
        self.item_path = os.path.join(temp_dir, self.item_id)

        self.gc.downloadItem(self.item_id, temp_dir, self.item_id)

        return self.item_path

    def cleanup(self):
        shutil.rmtree(os.path.dirname(self.item_path), ignore_errors=True)
