# Role-Based Access Control

The Level 2 platform uses server-enforced role-based access control (RBAC). The frontend uses the same permission list to disable navigation that is not available to the signed-in user, but the API remains the authorization boundary.

## Roles

| Role | Operational access | Additional access |
| --- | --- | --- |
| Viewer | Overview and production flow | None |
| Operator | Viewer access, historian, and alarms | None |
| Shift Supervisor | Operator access | Alarm acknowledgement and reports |
| Automation Engineer | Overview, production, historian, and alarms | PLC diagnostics and configuration viewing |
| Administrator | All platform permissions | User, role, and configuration management |

Each Django user is assigned to one managed group named `Level2:<ROLE>`. A user without a managed role is treated as a Viewer. Django superusers are always treated as Administrators.

## Administration API

- `GET /api/v1/access/roles` returns the role and permission matrix.
- `GET /api/v1/access/users` lists user accounts and assigned roles.
- `POST /api/v1/access/users` creates a user.
- `PATCH /api/v1/access/users/<id>` changes a role, display name, active status, or password.

All four operations require the `users.manage` permission. An administrator cannot remove their own administrator role or deactivate their own account.

## Bootstrap administrator

The API container creates the managed groups during startup and assigns the configured bootstrap account a role. Set the following values in `.env`:

```dotenv
DJANGO_BOOTSTRAP_USERNAME=OP-4109
DJANGO_BOOTSTRAP_PASSWORD=replace-with-a-strong-password
DJANGO_BOOTSTRAP_DISPLAY_NAME=Level 2 Administrator
DJANGO_BOOTSTRAP_ROLE=ADMINISTRATOR
```

The bootstrap process does not overwrite the password of an existing user. Password and role changes can therefore be managed through the Access Control screen after the initial deployment.

## Operational notes

- Disable an account instead of deleting it to preserve audit relationships.
- Assign Automation Engineer only to personnel who need PLC source, packet, or system-map diagnostics.
- Use Shift Supervisor for production leadership; it does not include PLC or user administration.
- Server-side role changes take effect on the next API request because authorization is resolved from the database rather than embedded in the JWT. The affected user should refresh the UI to update disabled navigation items.
