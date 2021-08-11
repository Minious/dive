import type { GirderModel } from '@girder/components/src';

import { DatasetMetaMutable, SaveAttributeArgs } from 'dive-common/apispec';
import { DatasetSourceMedia, GirderMetadataStatic } from 'platform/web-girder/constants';
import girderRest from 'platform/web-girder/plugins/girder';

interface HTMLFile extends File {
  webkitRelativePath?: string;
}

function getDataset(folderId: string) {
  return girderRest.get<GirderMetadataStatic>(`dive_dataset/${folderId}`);
}

function getDatasetMedia(folderId: string) {
  return girderRest.get<DatasetSourceMedia>(`dive_dataset/${folderId}/media`);
}

function clone({ folderId, name, parentFolderId }: {
  folderId: string;
  parentFolderId: string;
  name?: string;
}) {
  return girderRest.post<GirderModel>('dive_dataset', null, {
    params: { cloneId: folderId, parentFolderId, name },
  });
}

function makeViameFolder({
  folderId, name, fps, type,
}: {
  folderId: string;
  name: string;
  fps: number;
  type: string;
}) {
  return girderRest.post(
    '/folder',
    `metadata=${JSON.stringify({
      fps,
      type,
    })}`,
    {
      params: { parentId: folderId, name },
    },
  );
}

async function importAnnotationFile(parentId: string, path: string, file?: HTMLFile) {
  if (file === undefined) {
    return false;
  }
  const resp = await girderRest.post('/file', null, {
    params: {
      parentType: 'folder',
      parentId,
      name: file.name,
      size: file.size,
      mimeType: file.type,
    },
  });
  if (resp.status === 200) {
    const uploadResponse = await girderRest.post('file/chunk', file, {
      params: {
        uploadId: resp.data._id,
        offset: 0,
      },
      headers: { 'Content-Type': 'application/octet-stream' },
    });
    if (uploadResponse.status === 200) {
      const final = await girderRest.post(`viame/postprocess/${parentId}`, null, {
        params: {
          skipJobs: true,
        },
      });
      if (final.status === 200) {
        return true;
      }
    }
  }
  return false;
}

function saveAttributes(folderId: string, args: SaveAttributeArgs) {
  return girderRest.patch(`/dive_dataset/${folderId}/attributes`, args);
}

function saveMetadata(folderId: string, metadata: DatasetMetaMutable) {
  return girderRest.patch(`/dive_dataset/${folderId}`, metadata);
}

interface ValidationResponse {
  ok: boolean;
  type: 'video' | 'image-sequence';
  media: string[];
  annotations: string[];
  message: string;
}

function validateUploadGroup(names: string[]) {
  return girderRest.post<ValidationResponse>('dive_dataset/validate_files', names);
}


export {
  clone,
  getDataset,
  getDatasetMedia,
  importAnnotationFile,
  makeViameFolder,
  saveAttributes,
  saveMetadata,
  validateUploadGroup,
};
