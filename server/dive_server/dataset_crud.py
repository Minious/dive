"""
CRUD operations for the dataset REST view
"""
from typing import List, Optional

from girder.models.folder import Folder
from girder.models.item import Item
from girder.utility import ziputil
from pydantic.main import BaseModel

from dive_server import utils
from dive_utils import constants, fromMeta, models, types


def get_url(file: types.GirderModel, modelType='file') -> str:
    return f"api/v1/{modelType}/{str(file['_id'])}/download"


def get_dataset(
    dsFolder: types.GirderModel, user: types.GirderModel
) -> models.GirderMetadataStatic:
    """
    Transform a girder folder into a dataset metadata object
    """
    videoUrl = None
    imageData: List[models.FrameImage] = []
    utils.verify_dataset(dsFolder)
    source_type = fromMeta(dsFolder, constants.TypeMarker)

    if source_type == constants.VideoType:
        # Find a video tagged with an h264 codec left by the transcoder
        videoItem = Item().findOne(
            {
                'folderId': utils.getCloneRoot(user, dsFolder)['_id'],
                'meta.codec': 'h264',
                'meta.source_video': {'$in': [None, False]},
            }
        )
        if videoItem:
            videoFile = Item().childFiles(videoItem)[0]
            videoUrl = get_url(videoFile)
    elif source_type == constants.ImageSequenceType:
        imageData = [
            models.FrameImage(
                url=get_url(image, modelType='item'),
                filename=image['name'],
            )
            for image in utils.valid_images(dsFolder, user)
        ]
    else:
        raise ValueError(f'Unrecognized source type: {source_type}')

    return models.GirderMetadataStatic(
        id=str(dsFolder['_id']),
        imageData=imageData,
        videoUrl=videoUrl,
        createdAt=str(dsFolder['created']),
        name=dsFolder['name'],
        **dsFolder['meta'],
    )


class MetadataMutableUpdateArgs(models.MetadataMutable):
    """Update schema for mutable metadata fields"""

    class Config:
        extra = 'forbid'


def update_metadata(dsFolder: types.GirderModel, data: dict):
    """
    Update mutable metadata
    """
    utils.verify_dataset(dsFolder)
    validated: MetadataMutableUpdateArgs = utils.get_validated_model(
        MetadataMutableUpdateArgs, **data
    )
    for name, value in validated.dict(exclude_none=True).items():
        dsFolder['meta'][name] = value
    Folder().save(dsFolder)
    return dsFolder['meta']


class AttributeUpdateArgs(BaseModel):
    upsert: List[models.Attribute] = []
    delete: List[str] = []

    class Config:
        extra = 'forbid'


def update_attributes(dsFolder: types.GirderModel, data: dict):
    """
    Upsert or delete attributes
    """
    utils.verify_dataset(dsFolder)
    validated: AttributeUpdateArgs = utils.get_validated_model(AttributeUpdateArgs, **data)
    attributes_dict = fromMeta(dsFolder, 'attributes', {})

    for attribute_id in validated.delete:
        attributes_dict.pop(str(attribute_id), None)
    for attribute in validated.upsert:
        attributes_dict[str(attribute.key)] = validated.dict(exclude_none=True)

    upserted_len = len(validated.delete)
    deleted_len = len(validated.upsert)

    if upserted_len or deleted_len:
        update_metadata(dsFolder, {'attributes': attributes_dict})

    return {
        "updated": upserted_len,
        "deleted": deleted_len,
    }


def export_dataset_zipstream(
    dsFolder: types.GirderModel,
    user: types.GirderModel,
    includeMedia: bool,
    includeDetections: bool,
    excludeBelowThreshold: bool,
    typeFilter: Optional[List[str]],
):
    _, gen = utils.get_annotation_csv_generator(dsFolder, user, excludeBelowThreshold, typeFilter)
    mediaFolder = utils.getCloneRoot(user, dsFolder)
    source_type = fromMeta(mediaFolder, constants.TypeMarker)
    mediaRegex = None
    if source_type == constants.ImageSequenceType:
        mediaRegex = constants.imageRegex
    elif source_type == constants.VideoType:
        mediaRegex = constants.videoRegex

    def makeMetajson():
        yield get_dataset(dsFolder, user).json(exclude_none=True)

    def stream():
        z = ziputil.ZipGenerator(dsFolder['name'])

        # Always add the metadata file
        z.addFile(makeMetajson, 'meta.json')

        if includeMedia:
            # Add media
            for item in Folder().childItems(
                mediaFolder,
                filters={"lowerName": {"$regex": mediaRegex}},
            ):
                for (path, file) in Item().fileList(item):
                    for data in z.addFile(file, path):
                        yield data
                    break  # Media items should only have 1 valid file

        if includeDetections:
            # add JSON detections
            for (path, file) in Folder().fileList(
                dsFolder,
                user=user,
                subpath=False,
                mimeFilter={'application/json'},
            ):
                for data in z.addFile(file, path):
                    yield data
            # add CSV detections
            for data in z.addFile(gen, "output_tracks.csv"):
                yield data
        yield z.footer()

    return stream
