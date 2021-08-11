import type { Module } from 'vuex';
import type { GirderMetadata } from 'platform/web-girder/constants';
import { getDataset, getDatasetMedia, getFolder } from 'platform/web-girder/api';
import type { DatasetState, RootState } from './types';

const datasetModule: Module<DatasetState, RootState> = {
  namespaced: true,
  state: {
    meta: null,
  },
  mutations: {
    set(state, { dataset }: { dataset: GirderMetadata }) {
      state.meta = dataset;
    },
  },
  actions: {
    async load({ commit }, datasetId: string): Promise<GirderMetadata> {
      const [folder, girderDataset, media] = await Promise.all([
        getFolder(datasetId),
        getDataset(datasetId),
        getDatasetMedia(datasetId),
      ]);
      const dsMeta = {
        ...girderDataset.data,
        ...media.data,
        videoUrl: media.data.video?.url,
      };
      commit('set', { dataset: dsMeta });
      commit('Location/setLocation', {
        _id: folder.data.parentId,
        _modelType: folder.data.parentCollection,
      }, { root: true });
      return dsMeta;
    },
  },
};

export default datasetModule;
