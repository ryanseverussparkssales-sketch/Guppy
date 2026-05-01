# TanStack Query Migration Guide for Guppy

**Purpose:** Reference guide for future view migrations and maintenance  
**Last Updated:** 2026-04-25  
**Status:** FINALIZED

---

## Quick Reference: Before & After

### Data Fetching

**BEFORE:**
```typescript
const [data, setData] = useState(null)
const [loading, setLoading] = useState(true)
const [error, setError] = useState(null)

const fetchData = async () => {
  try {
    const res = await api.get('/endpoint')
    setData(res.data)
  } catch (e) {
    setError('Failed to load')
  } finally {
    setLoading(false)
  }
}

useEffect(() => {
  fetchData()
}, [])
```

**AFTER:**
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: QK.myData,
  queryFn: async () => (await api.get('/endpoint')).data,
})
```

**Benefits:**
- ✅ Automatic caching
- ✅ Automatic refetch on window focus
- ✅ Stale time management
- ✅ No manual error handling
- ✅ Fewer lines of code

---

### Mutations (Write Operations)

**BEFORE:**
```typescript
const [saving, setSaving] = useState(false)

const handleSave = async (payload) => {
  setSaving(true)
  try {
    await api.post('/endpoint', payload)
    // manually refetch
    const res = await api.get('/other-endpoint')
    setOtherData(res.data)
  } catch {
    // handle error
  } finally {
    setSaving(false)
  }
}
```

**AFTER:**
```typescript
const mutation = useMutation({
  mutationFn: (payload) => api.post('/endpoint', payload),
  onSuccess: () => qc.invalidateQueries({ queryKey: QK.otherData }),
})

const handleSave = async (payload) => {
  await mutation.mutateAsync(payload)
}
```

**Benefits:**
- ✅ Automatic refetch after mutation
- ✅ Automatic error handling
- ✅ Mutation state (`isPending`, `error`) included
- ✅ Query cache invalidation built-in

---

## Guppy-Specific Patterns

### Pattern 1: Basic Query Hook

**Location:** `web/src/api/queries.ts`  
**Example:** `useTools()`, `useProviders()`, `useSettings()`

```typescript
export function useTools(opts?: Partial<UseQueryOptions<Tool[]>>) {
  return useQuery<Tool[]>({
    queryKey: QK.tools,
    queryFn: async () => {
      const data = (await api.get('/api/tools')).data
      return (Array.isArray(data) ? data : []).map((t: unknown) => ToolSchema.parse(t))
    },
    staleTime: 60_000,  // 1 minute
    ...opts,
  })
}
```

**In Components:**
```typescript
const { data: tools, isLoading, error } = useTools()

if (isLoading) return <Spinner />
if (error) return <ErrorAlert message={error.message} />
return <ToolsList items={tools ?? []} />
```

---

### Pattern 2: Mutation with Refetch

**Location:** `web/src/api/queries.ts`  
**Example:** `useSetToolEnabled()`, `useStoreCredential()`

```typescript
export function useSetToolEnabled() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ toolId, enabled }: { toolId: string; enabled: boolean }) =>
      api.post(`/api/tools/${toolId}/${enabled ? 'enable' : 'disable'}`),
    // Automatic refetch when mutation succeeds
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.tools }),
  })
}
```

**In Components:**
```typescript
const mutation = useSetToolEnabled()

const handleToggle = async (toolId: string, enabled: boolean) => {
  try {
    await mutation.mutateAsync({ toolId, enabled })
    toast.success(`Tool ${enabled ? 'enabled' : 'disabled'}`)
  } catch (error) {
    toast.error('Failed to toggle tool')
  }
}
```

---

### Pattern 3: Parameterized Query (Lazy Loading)

**Location:** `web/src/api/queries.ts`  
**Example:** `useMCPServerTools(serverId)`, `usePullStatus(jobId)`

```typescript
export function useMCPServerTools(serverId: string) {
  return useQuery({
    queryKey: QK.mcpTools(serverId),
    queryFn: async () => (await api.get(`/api/mcp/servers/${serverId}/tools`)).data.tools ?? [],
    staleTime: 60_000,
    enabled: !!serverId,  // Only fetch when serverId is provided
  })
}
```

**In Components:**
```typescript
// Only fetch when expanded is true
const { data: tools, isLoading } = useMCPServerTools(expanded ? serverId : "")

// Or manually control
const [shouldFetch, setShouldFetch] = useState(false)
const { data: tools } = useMCPServerTools(shouldFetch ? serverId : "")
```

---

### Pattern 4: Long-Running Operations (Polling)

**Location:** `web/src/api/queries.ts`  
**Example:** `usePullStatus(jobId)`

```typescript
export function usePullStatus(jobId: string | null) {
  return useQuery<PullStatus>({
    queryKey: QK.pullJob(jobId ?? ''),
    queryFn: async () =>
      PullStatusSchema.parse((await api.get(`/api/models/pull/${jobId}`)).data),
    enabled: !!jobId,
    // Refetch every 1 second while not done
    refetchInterval: (q) => (q.state.data?.done ? false : 1000),
    staleTime: 0,
  })
}
```

**In Components:**
```typescript
const { data: pullStatus } = usePullStatus(pullJobId)

// Stop polling when done
if (pullStatus?.done) {
  setPullJobId(null)
  // Refetch parent query
  qc.invalidateQueries({ queryKey: QK.providers })
}
```

---

## Query Keys Registry (QK)

**Location:** `web/src/api/queries.ts` (lines 34–47)

```typescript
export const QK = {
  // Simple keys
  settings:   ['settings'] as const,
  providers:  ['providers'] as const,
  tools:      ['tools'] as const,
  mcpServers: ['mcpServers'] as const,
  metrics:    ['metrics'] as const,
  status:     ['status'] as const,
  
  // Parameterized keys (for polling, lazy loading, etc.)
  pullJob:    (id: string) => ['pullJob', id] as const,
  mcpTools:   (id: string) => ['mcpTools', id] as const,
} as const
```

**When to Use:**
- ✅ **Use QK:** Always reference keys through the registry
- ❌ **Don't hardcode:** Avoid `['tools']` in components; use `QK.tools`
- ✅ **Why:** Refactoring cache strategy is one place change vs. 10 places

**Invalidation Example:**
```typescript
// Single key
qc.invalidateQueries({ queryKey: QK.tools })

// Multiple keys
qc.invalidateQueries({ queryKey: QK.providers })
qc.invalidateQueries({ queryKey: QK.tools })

// All "pull" jobs
qc.invalidateQueries({ queryKey: QK.pullJob('') })
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting `onSuccess` Refetch

❌ **Wrong:**
```typescript
const mutation = useMutation({
  mutationFn: (data) => api.post('/save', data),
  // Mutation succeeds but cache is stale!
})
```

✅ **Right:**
```typescript
const mutation = useMutation({
  mutationFn: (data) => api.post('/save', data),
  onSuccess: () => qc.invalidateQueries({ queryKey: QK.data }),
})
```

---

### Pitfall 2: Over-Using `useState` for Async State

❌ **Wrong:**
```typescript
const [saving, setSaving] = useState(false)
const [error, setError] = useState(null)

// Now you have duplicate state (mutation.isPending + saving)
```

✅ **Right:**
```typescript
// Use mutation state directly
const mutation = useMutation(...)
// Access: mutation.isPending, mutation.error
```

---

### Pitfall 3: Polling Every Render

❌ **Wrong:**
```typescript
useEffect(() => {
  const interval = setInterval(() => api.get(...), 1000)
  return () => clearInterval(interval)
}, []) // Poll only once
```

✅ **Right:**
```typescript
useQuery({
  queryFn: ...,
  refetchInterval: 1000, // TanStack Query manages this
})
```

---

### Pitfall 4: Disabled Queries Still Refetch on Window Focus

❌ **Wrong:**
```typescript
const { data: tools } = useQuery({
  enabled: !!serverId,
  refetchOnWindowFocus: true, // Will refetch even if disabled!
})
```

✅ **Right:**
```typescript
const { data: tools } = useQuery({
  queryKey: QK.mcpTools(serverId),
  enabled: !!serverId,
  // Default: refetchOnWindowFocus only applies if query is enabled
})
```

---

## State Management Best Practices

### What Goes in TanStack Query?

✅ **Remote Server State**
- API responses
- Settings from backend
- Lists of items
- Anything that changes on server

❌ **Local UI State**
- Form inputs
- Toggle states
- Expanded/collapsed panels
- Modal open/close

**Example:**
```typescript
// ✅ Server state → TanStack Query
const { data: tools } = useTools()

// ✅ Local state → useState
const [searchQuery, setSearchQuery] = useState('')
const [selectedCategory, setSelectedCategory] = useState(null)

// Derived state (no useState needed)
const filtered = tools?.filter(t =>
  t.name.includes(searchQuery) &&
  (!selectedCategory || t.category === selectedCategory)
)
```

---

## Error Handling Patterns

### Pattern 1: Query Error Display

```typescript
const { data, error, isLoading } = useQuery(...)

if (error) {
  return (
    <div className="error">
      <AlertCircle className="w-5 h-5" />
      <p>Failed to load: {error.message}</p>
      <button onClick={() => refetch()}>Retry</button>
    </div>
  )
}
```

### Pattern 2: Mutation Error Toast

```typescript
const mutation = useMutation({
  mutationFn: ...,
  onError: (error) => {
    toast.error(error.message || 'Operation failed')
  },
})

await mutation.mutateAsync(payload)
```

### Pattern 3: Fallback UI

```typescript
const { data = EMPTY_TOOLS } = useTools()
// Use fallback if data is undefined

return <ToolsList items={data} />
```

---

## Testing Patterns

### Mocking TanStack Query

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
})

const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
)

test('loads tools', async () => {
  const { getByText } = render(<ToolsView />, { wrapper })
  expect(getByText('Loading')).toBeInTheDocument()
  // Wait for query to resolve
  await waitFor(() => expect(getByText('Tool Name')).toBeInTheDocument())
})
```

---

## Performance Tips

### 1. Stale Time Tuning

```typescript
useQuery({
  queryKey: QK.tools,
  queryFn: ...,
  staleTime: 60_000,  // 1 minute: don't refetch within this window
  gcTime: 5 * 60_000, // 5 minutes: keep in cache for this long
})
```

- **Longer `staleTime`:** Fewer network requests, but potentially stale data
- **Shorter `staleTime`:** Fresh data, but more network overhead

### 2. Separate Query Keys for Different Purposes

```typescript
// Good: Different stale times for different uses
QK.settings    // 30 seconds (user can change anytime)
QK.tools       // 1 minute (less frequently changing)
QK.providers   // 15 seconds (status can change)
```

### 3. Avoid Refetching on Mount

```typescript
// By default, TanStack Query refetches on mount if stale
// If you want to avoid this:
useQuery({
  queryKey: QK.tools,
  queryFn: ...,
  staleTime: Infinity,  // Never stale
  refetchOnMount: false, // Don't refetch on mount
})
```

---

## Debugging with React Query DevTools

```typescript
// Add to App.tsx (dev only)
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

<QueryClientProvider client={queryClient}>
  <App />
  <ReactQueryDevtools initialIsOpen={false} />
</QueryClientProvider>
```

**What You Can See:**
- All active queries/mutations
- Cache state (fresh/stale)
- Request/response data
- Network timings
- Error messages

---

## Checklist for Migrating a View

- [ ] Replace all `useState` for server data with `useQuery`
- [ ] Replace all `useEffect` fetches with query `queryFn`
- [ ] Replace all mutations with `useMutation` + `onSuccess` refetch
- [ ] Remove manual error handling; use query `error` state
- [ ] Remove manual loading state; use query `isLoading`
- [ ] Add toast notifications for mutations
- [ ] Test with React Query DevTools
- [ ] Verify `npm run build` completes
- [ ] Run `npx tsc --noEmit`

---

## Resources

**Official Docs:**
- https://tanstack.com/query/latest
- https://tanstack.com/query/latest/docs/framework/react/overview

**Guppy-Specific:**
- `web/src/api/queries.ts` - All hooks
- `web/src/views/AdminPanel.tsx` - Reference implementation
- `MIGRATION_TRANCHE_3_SUMMARY.md` - Completed work

**React Query Devtools:**
- https://tanstack.com/query/latest/docs/devtools/overview

---

**Last Updated:** 2026-04-25  
**Maintained By:** Claude Agent (Tranche 3)  
**Status:** REFERENCE COMPLETE
