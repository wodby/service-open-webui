# Open WebUI service for Kubernetes on Wodby

Run Open WebUI as a reusable Kubernetes application service with Wodby.

This repository defines the Wodby service manifest and operational
configuration for Open WebUI, a self-hosted chat interface for OpenAI-compatible
model APIs.

- [Browse Wodby services](https://wodby.com/services)
- [Wodby service documentation](https://wodby.com/docs/2.0/services/)
- [Service manifest reference](https://wodby.com/docs/2.0/services/template/)

## Wodby stacks using this service

- [Open WebUI application stack](https://github.com/wodby/stack-open-webui)

## Service overview

| Property | Manifest configuration |
| --- | --- |
| Service name | `open-webui` |
| Type | Application service |
| Versions | Open WebUI `0.13` from the official `ghcr.io/open-webui/open-webui` image |
| Database | Required PostgreSQL link |
| Models | Optional link to an OpenAI-compatible service such as vLLM; other providers are added in Open WebUI |
| Administrator | Created on the first start from the required admin email and password settings |
| HTTP endpoint | Port `8080`; HTTPS redirect; no route timeouts for streamed answers |
| Persistent storage | 10 GB by default for uploads, the document search index, and caches |
| Scaling | Fixed to one replica |

The image is published for `linux/amd64` and `linux/arm64`.

## Use this service

Use this service through the [Open WebUI application stack](https://github.com/wodby/stack-open-webui), or reference `open-webui` from a
custom Wodby stack.

A service is a reusable component and does not deploy by itself. The stack
defines its links, settings, versions, resources, and relationship to the rest
of the application.

## Settings saved by Open WebUI

Open WebUI saves most of its configuration, including model connections, to its
database on the first start and then ignores the matching environment
variables. Settings changed in **Admin Panel → Settings** survive redeploys.
Adding the model link to an existing app therefore does not add the connection;
add it in Open WebUI instead.

## Storage and backups

Users, chats, and settings are in the linked PostgreSQL database. Uploaded
files and the document search index are on the volume. Back up both together.

## Maintain a custom version

1. Fork this repository.
2. Edit the service manifest and referenced files.
3. Import the repository as a [Git-backed service](https://wodby.com/docs/2.0/services/create/#create-a-git-backed-service).
4. Reference the service from a stack manifest.

Keep service, workload, container, endpoint, link, volume, config, and
derivative names stable unless dependent stacks and app-level overrides are
updated at the same time.

Validate the manifests with:

```bash
wodby service validate-manifest service.yml --org <org-id>
```

Run the offline Helm contract test with:

```bash
python3 -m unittest discover -s tests
```

See the [service manifest reference](https://wodby.com/docs/2.0/services/template/) and the [managed services index](https://github.com/wodby/services).
