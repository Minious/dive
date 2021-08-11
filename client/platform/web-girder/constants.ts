import { GirderModel } from '@girder/components/src';
import {
  DatasetMeta, DatasetMetaMutable, DatasetType, FrameImage,
} from 'dive-common/apispec';

/**
 * Static properties loaded from the girder folder data/metadata
 */

interface GirderMetadataStatic extends DatasetMetaMutable {
  id: string;
  name: string;
  createdAt: string;
  type: Readonly<DatasetType>;
  fps: Readonly<number>;
  annotate: boolean;

  /* optional */
  originalFps?: number;
  ffprobe_info?: Record<string, string>;
  foreign_media_id?: string;
}

interface MediaResource extends FrameImage {
  id: string;
}

interface DatasetSourceMedia {
  imageData: MediaResource[];
  video?: MediaResource;
}
/** A girder folder model with dataset metadata */
interface GirderDatasetModel extends GirderModel {
  meta: GirderMetadataStatic;
}

/**
 * Full metadata including dynamic properties (image list, video url)
 */
type GirderMetadata = GirderMetadataStatic & DatasetMeta;

export {
  DatasetSourceMedia,
  GirderDatasetModel,
  GirderMetadataStatic,
  GirderMetadata,
};
