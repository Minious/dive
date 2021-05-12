import json
import urllib
from typing import List

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, setContentDisposition, setResponseHeader
from girder.constants import AccessType, TokenScope
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.utility import ziputil

from dive_server import multicam
from dive_server.serializers import viame
from dive_server.utils import (
    detections_file,
    detections_item,
    getCloneRoot,
    getTrackData,
    saveTracks,
    verify_dataset,
)
from dive_utils import fromMeta, models
from dive_utils.constants import (
    FPSMarker,
    ImageMimeTypes,
    ImageSequenceType,
    TypeMarker,
    VideoMimeTypes,
    VideoType,
    safeImageRegex,
)


class ViameDetection(Resource):
    def __init__(self):
        super(ViameDetection, self).__init__()
        self.resourceName = "viame_detection"
        self.route("GET", (), self.get_detection)
        self.route("PUT", (), self.save_detection)
        self.route("GET", ("clip_meta",), self.get_clip_meta)
        self.route("GET", ("multi_meta",), self.get_multi_meta)
        self.route("GET", (":id", "export"), self.get_export_urls)
        self.route("GET", (":id", "export_detections"), self.export_detections)
        self.route("GET", (":id", "export_all"), self.export_all)

    def _get_clip_meta(self, folder):
        videoUrl = None
        video = None

        # Find a video tagged with an h264 codec left by the transcoder
        item = Item().findOne(
            {
                'folderId': getCloneRoot(self.getCurrentUser(), folder)['_id'],
                'meta.codec': 'h264',
                'meta.source_video': {
                    '$in': [
                        # In a previous version, source_video was unset
                        None,
                        False,
                    ]
                },
            }
        )
        if item:
            video = Item().childFiles(item)[0]
            videoUrl = (
                f'/api/v1/file/{str(video["_id"])}/download?contentDisposition=inline'
            )

        return {
            'folder': folder,
            'detection': detections_item(folder),
            'video': video,
            'videoUrl': videoUrl,
        }

    def _generate_detections(self, folder, excludeBelowThreshold):
        file = detections_file(folder, strict=True)

        # TODO: deprecated, remove after we migrate everyone to json
        if "csv" in file["exts"]:
            return File().download(file)

        filename = ".".join([file["name"].split(".")[:-1][0], "csv"])

        fps = None
        imageFiles = None
        source_type = fromMeta(folder, TypeMarker)
        if source_type == VideoType:
            fps = fromMeta(folder, FPSMarker)
        elif source_type == ImageSequenceType:
            imageFiles = [
                f['name']
                for f in Folder()
                .childItems(folder, filters={"lowerName": {"$regex": safeImageRegex}})
                .sort("lowerName")
            ]
        thresholds = fromMeta(folder, "confidenceFilters", {})
        track_dict = getTrackData(file)

        def downloadGenerator():
            for data in viame.export_tracks_as_csv(
                track_dict,
                excludeBelowThreshold,
                thresholds=thresholds,
                filenames=imageFiles,
                fps=fps,
            ):
                yield data

        return filename, downloadGenerator

    @access.user
    @autoDescribeRoute(
        Description("Export VIAME data")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def get_export_urls(self, folder, excludeBelowThreshold):
        verify_dataset(folder)
        folderId = str(folder['_id'])
        mediaFolderId = getCloneRoot(self.getCurrentUser(), folder)['_id']
        export_all = f'/api/v1/folder/{folderId}/download'
        export_media = None
        export_detections = None

        clipMeta = self._get_clip_meta(folder)
        detection = clipMeta.get('detection')
        if detection:
            export_detections = (
                f'/api/v1/viame_detection/{folderId}/export_detections'
                f'?excludeBelowThreshold={excludeBelowThreshold}'
            )
            export_all = (
                f'/api/v1/viame_detection/{folderId}/export_all'
                f'?excludeBelowThreshold={excludeBelowThreshold}'
            )

        source_type = fromMeta(folder, TypeMarker)
        if source_type == VideoType:
            params = {
                'mimeFilter': json.dumps(list(VideoMimeTypes)),
            }
            export_media = f'/api/v1/folder/{mediaFolderId}/download?{urllib.parse.urlencode(params)}'
        elif source_type == ImageSequenceType:
            params = {
                'mimeFilter': json.dumps(list(ImageMimeTypes)),
            }
            export_media = f'/api/v1/folder/{mediaFolderId}/download?{urllib.parse.urlencode(params)}'

        # No-copy import data does not support mimeFilter.
        # We cannot detect which collections are from no-copy imported data, so
        # disable all image download from collections
        if folder['baseParentType'] == 'collection':
            export_media = None

        return {
            'mediaType': source_type,
            'exportAllUrl': export_all,
            'exportMediaUrl': export_media,
            'exportDetectionsUrl': export_detections,
            'currentThresholds': fromMeta(folder, "confidenceFilters", {}),
        }

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Export detections of a clip into CSV format.")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def export_detections(self, folder, excludeBelowThreshold):
        verify_dataset(folder)
        filename, gen = self._generate_detections(folder, excludeBelowThreshold)
        setContentDisposition(filename)
        return gen

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Export detections of a clip into CSV format.")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def export_all(self, folder, excludeBelowThreshold):
        verify_dataset(folder)
        _, gen = self._generate_detections(folder, excludeBelowThreshold)
        setResponseHeader('Content-Type', 'application/zip')
        setContentDisposition(folder['name'] + '.zip')
        user = self.getCurrentUser()
        mediaFolder = getCloneRoot(user, folder)

        def stream():
            z = ziputil.ZipGenerator(folder['name'])
            # add media
            for (path, file) in Folder().fileList(
                mediaFolder,
                user=user,
                subpath=False,
                mimeFilter=VideoMimeTypes.union(ImageMimeTypes),
            ):
                for data in z.addFile(file, path):
                    yield data
            # add JSON detections
            for (path, file) in Folder().fileList(
                folder,
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

    @access.user
    @autoDescribeRoute(
        Description("Get detections of a clip").modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.READ,
        )
    )
    def get_detection(self, folder):
        verify_dataset(folder)
        file = detections_file(folder)
        if file is None:
            return {}
        if "csv" in file["exts"]:
            raise RestException(
                'Cannot get detections until postprocessing is complete.'
            )
        return File().download(file, contentDisposition="inline")

    @access.user
    @autoDescribeRoute(
        Description("").modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.READ,
        )
    )
    def get_clip_meta(self, folder):
        verify_dataset(folder)
        return self._get_clip_meta(folder)

    @access.user
    @autoDescribeRoute(
        Description("").modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.READ,
        )
    )
    def get_multi_meta(self, folder):
        verify_dataset(folder)
        if folder['meta']['multiCam'] is not None:
            multiCam = folder['meta']['multiCam']
            base = multiCam['display']
            base_meta = multiCam['cameras'][base]
            if base_meta is not None:
                return {
                    'folderId': base_meta['originalBaseId'],
                    'type': base_meta['type'],
                }
        return {}

    @access.user
    @autoDescribeRoute(
        Description("")
        .modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.WRITE,
        )
        .jsonParam(
            "tracks", "upsert and delete tracks", paramType="body", requireObject=True
        )
    )
    def save_detection(self, folder, tracks):
        verify_dataset(folder)
        user = self.getCurrentUser()
        upsert: List[dict] = tracks.get('upsert', [])
        delete: List[str] = tracks.get('delete', [])
        track_dict = getTrackData(detections_file(folder))

        for track_id in delete:
            track_dict.pop(str(track_id), None)
        for track in upsert:
            validated: models.Track = models.Track(**track)
            track_dict[str(validated.trackId)] = validated.dict(exclude_none=True)

        upserted_len = len(upsert)
        deleted_len = len(delete)

        if upserted_len or deleted_len:
            saveTracks(folder, track_dict, user)

        return {
            "updated": upserted_len,
            "deleted": deleted_len,
        }
