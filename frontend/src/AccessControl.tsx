import { FormEvent, useCallback, useEffect, useState } from 'react'
import { authorizedFetch } from './auth'
import './access-control.css'

type RoleDefinition = {
  key: string
  label: string
  permissions: string[]
}

type AccessUser = {
  id: number
  username: string
  display_name: string
  role: string
  role_label: string
  permissions: string[]
  is_active: boolean
  last_login: string | null
}

type CreateUserForm = {
  username: string
  display_name: string
  password: string
  role: string
}

const emptyForm: CreateUserForm = {
  username: '',
  display_name: '',
  password: '',
  role: 'OPERATOR',
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json() as Record<string, unknown>
    if (typeof body.detail === 'string') return body.detail
    const first = Object.values(body)[0]
    if (Array.isArray(first)) return first.join(' ')
    if (typeof first === 'string') return first
  } catch {
    // The generic status message below is safe when the API has no JSON body.
  }
  return `Request failed (${response.status}).`
}

export function AccessControl({ currentUsername }: { currentUsername: string }) {
  const [roles, setRoles] = useState<RoleDefinition[]>([])
  const [permissionLabels, setPermissionLabels] = useState<Record<string, string>>({})
  const [users, setUsers] = useState<AccessUser[]>([])
  const [form, setForm] = useState<CreateUserForm>(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    setError('')
    const [rolesResponse, usersResponse] = await Promise.all([
      authorizedFetch('/api/v1/access/roles'),
      authorizedFetch('/api/v1/access/users'),
    ])
    if (!rolesResponse.ok) throw new Error(await errorMessage(rolesResponse))
    if (!usersResponse.ok) throw new Error(await errorMessage(usersResponse))
    const roleBody = await rolesResponse.json() as { roles: RoleDefinition[]; permission_labels: Record<string, string> }
    const userBody = await usersResponse.json() as { users: AccessUser[] }
    setRoles(roleBody.roles)
    setPermissionLabels(roleBody.permission_labels)
    setUsers(userBody.users)
  }, [])

  useEffect(() => {
    load().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load access control.'))
      .finally(() => setLoading(false))
  }, [load])

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = await authorizedFetch('/api/v1/access/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, is_active: true }),
      })
      if (!response.ok) throw new Error(await errorMessage(response))
      setForm(emptyForm)
      setNotice(`User ${form.username} created.`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to create user.')
    } finally {
      setSaving(false)
    }
  }

  async function updateUser(user: AccessUser, patch: Partial<Pick<AccessUser, 'role' | 'is_active'>>) {
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = await authorizedFetch(`/api/v1/access/users/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!response.ok) throw new Error(await errorMessage(response))
      const updated = await response.json() as AccessUser
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item))
      setNotice(`Access updated for ${updated.username}.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update user.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="access-page" aria-labelledby="access-title">
      <div className="page-heading access-heading">
        <div><span className="section-kicker">SECURITY &amp; AUTHORIZATION</span><h1 id="access-title">Access Control</h1><p>Role-based access for operators, supervisors, automation engineers, and administrators</p></div>
        <div className="access-policy"><span>RBAC</span><strong>Least Privilege</strong><small>Server-enforced permissions</small></div>
      </div>

      {error && <div className="api-notice access-message" role="alert">{error}</div>}
      {notice && <div className="access-message success" role="status">{notice}</div>}

      <div className="role-grid" aria-label="Role permission matrix">
        {roles.map((role) => <article className="role-card" key={role.key}>
          <div><span>{role.key.replace(/_/g, ' ')}</span><strong>{role.label}</strong></div>
          <small>{role.permissions.length} permissions</small>
          <ul>{role.permissions.map((permission) => <li key={permission}>{permissionLabels[permission] ?? permission}</li>)}</ul>
        </article>)}
      </div>

      <div className="access-layout">
        <section className="panel access-users-panel">
          <div className="panel-heading"><div><span className="section-kicker">USER DIRECTORY</span><h2>Users and Assigned Roles</h2></div><span className="access-count">{users.length} USERS</span></div>
          <div className="access-table-wrap">
            <table className="access-table">
              <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Last Login</th></tr></thead>
              <tbody>{users.map((user) => <tr key={user.id}>
                <td><strong>{user.display_name}</strong><small>{user.username}</small></td>
                <td><select aria-label={`Role for ${user.username}`} value={user.role} disabled={saving || user.username === currentUsername} onChange={(event) => updateUser(user, { role: event.target.value })}>{roles.map((role) => <option value={role.key} key={role.key}>{role.label}</option>)}</select></td>
                <td><label className="access-toggle"><input type="checkbox" checked={user.is_active} disabled={saving || user.username === currentUsername} onChange={(event) => updateUser(user, { is_active: event.target.checked })} /><span>{user.is_active ? 'Active' : 'Disabled'}</span></label></td>
                <td>{user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
              </tr>)}</tbody>
            </table>
          </div>
          {loading && <div className="access-loading">Loading access directory…</div>}
        </section>

        <section className="panel create-user-panel">
          <div className="panel-heading"><div><span className="section-kicker">NEW ACCOUNT</span><h2>Create User</h2></div></div>
          <form onSubmit={createUser} autoComplete="off">
            <label>Employee ID<input required autoComplete="off" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="OP-4109" /></label>
            <label>Display Name<input required autoComplete="off" value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} placeholder="Shift Operator" /></label>
            <label>Initial Password<input required minLength={8} type="password" autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Minimum 8 characters" /></label>
            <label>Role<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>{roles.map((role) => <option value={role.key} key={role.key}>{role.label}</option>)}</select></label>
            <button className="login-button" type="submit" disabled={saving}>{saving ? 'Applying…' : 'Create User'}</button>
          </form>
        </section>
      </div>
    </section>
  )
}
