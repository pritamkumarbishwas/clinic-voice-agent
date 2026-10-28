import { clinicApi } from "./base-api";

const KNOWLEDGE_LIST_TAG = { type: "Knowledge", id: "LIST" };

const knowledgeApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    listKnowledge: build.query({
      query: () => "/api/knowledge",
      providesTags: [KNOWLEDGE_LIST_TAG],
    }),
    createKnowledge: build.mutation({
      query: (document) => ({
        url: "/api/knowledge",
        method: "POST",
        body: document,
      }),
      invalidatesTags: [KNOWLEDGE_LIST_TAG],
    }),
    updateKnowledge: build.mutation({
      query: ({ knowledgeId, ...document }) => ({
        url: `/api/knowledge/${knowledgeId}`,
        method: "PUT",
        body: document,
      }),
      invalidatesTags: [KNOWLEDGE_LIST_TAG],
    }),
    deleteKnowledge: build.mutation({
      query: (knowledgeId) => ({
        url: `/api/knowledge/${knowledgeId}`,
        method: "DELETE",
      }),
      invalidatesTags: [KNOWLEDGE_LIST_TAG],
    }),
    searchKnowledge: build.mutation({
      query: ({ query, topK = 3 }) => ({
        url: "/api/knowledge/search",
        method: "POST",
        body: { query, top_k: topK },
      }),
    }),
    uploadKnowledge: build.mutation({
      query: ({ file, title = "", category = "general", active = true }) => {
        const body = new FormData();
        body.append("file", file);
        body.append("title", title);
        body.append("category", category);
        body.append("active", String(active));
        return {
          url: "/api/knowledge/upload",
          method: "POST",
          body,
        };
      },
      invalidatesTags: [KNOWLEDGE_LIST_TAG],
    }),
  }),
  overrideExisting: false,
});

export const {
  useCreateKnowledgeMutation,
  useDeleteKnowledgeMutation,
  useListKnowledgeQuery,
  useSearchKnowledgeMutation,
  useUpdateKnowledgeMutation,
  useUploadKnowledgeMutation,
} = knowledgeApi;
