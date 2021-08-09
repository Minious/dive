from typing import List

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, setContentDisposition, setResponseHeader
from girder.constants import AccessType, TokenScope
from girder.models.folder import Folder

from . import dataset_crud

DatasetModelParam = {
    'description': "dataset id",
    'model': Folder,
    'paramType': 'path',
    'required': True,
}


class DatasetResource(Resource):
    """
    RESTful Dataset resource
    """

    def __init__(self, resourceName):
        super(DatasetResource, self).__init__()
        self.resourceName = resourceName

        self.route("GET", (":id",), self.get_meta)
        self.route("GET", (":id", "export"), self.export)

        self.route("PATCH", (":id", "metadata"), self.patch_metadata)
        self.route("PATCH", (":id", "attributes"), self.patch_attributes)

    @access.user
    @autoDescribeRoute(
        Description("Get dataset metadata").modelParam(
            "id", level=AccessType.READ, **DatasetModelParam
        )
    )
    def get_meta(self, folder):
        # TODO idea -- add a "camera" query param
        return dataset_crud.get_dataset(folder, self.getCurrentUser()).dict(exclude_none=True)

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Export everything in a dataset")
        .modelParam("id", level=AccessType.READ, **DatasetModelParam)
        .param(
            "includeMedia",
            "Include media content",
            paramType="query",
            dataType="boolean",
            default=True,
        )
        .param(
            "includeDetections",
            "Include annotation content",
            paramType="query",
            dataType="boolean",
            default=True,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
        .jsonParam(
            "typeFilter",
            "List of track types to filter by",
            paramType="query",
            required=False,
            default=[],
            requireArray=True,
        )
    )
    def export(
        self,
        folder,
        includeMedia: bool,
        includeDetections: bool,
        excludeBelowThreshold: bool,
        typeFilter: List[str],
    ):
        setResponseHeader('Content-Type', 'application/zip')
        setContentDisposition(folder['name'] + '.zip')
        return dataset_crud.export_dataset_zipstream(
            folder,
            self.getCurrentUser(),
            includeMedia=includeMedia,
            includeDetections=includeDetections,
            excludeBelowThreshold=excludeBelowThreshold,
            typeFilter=typeFilter,
        )

    @access.user
    @autoDescribeRoute(
        Description("Update mutable metadata fields")
        .modelParam("id", level=AccessType.WRITE, **DatasetModelParam)
        .jsonParam(
            "data",
            description="JSON with the metadata to set",
            requireObject=True,
            paramType="body",
        )
    )
    def patch_metadata(self, folder, data):
        return dataset_crud.update_dataset(folder, data)

    @access.user
    @autoDescribeRoute(
        Description("Update set of possible attributes")
        .modelParam("id", level=AccessType.WRITE, **DatasetModelParam)
        .jsonParam(
            "data",
            description="upsert and delete",
            requireObject=True,
            paramType="body",
        )
    )
    def patch_attributes(self, folder, data):
        return dataset_crud.update_attributes(folder, data)
