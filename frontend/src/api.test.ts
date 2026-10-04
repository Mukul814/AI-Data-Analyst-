import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

describe('API client',()=>{
 afterEach(()=>vi.unstubAllGlobals());
 it('creates projects with the validated JSON payload',async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'p1',name:'North Star'})});
  vi.stubGlobal('fetch',fetchMock);
  await api.createProject('North Star');
  expect(fetchMock.mock.calls[0][0]).toContain('/projects');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({name:'North Star'});
 });
});
