# One-container public deployment

Work from the original repository: `nasa-space-apps`. The root Dockerfile builds
Next.js and the CPU PyTorch API together. Only port 8080 is exposed. Next.js
proxies prediction requests to Flask on container-local port 5000. The runtime
downloads models from the private S3 bucket; the image contains no ML checkpoint
or prepared reference dataset. Your Mac can be turned off after deployment.

## Verify the image

With Docker Desktop or Docker Engine running, from the repository root:

```sh
docker build -t pyroclast-fullstack .
docker run --rm -p 8080:8080 pyroclast-fullstack
```

Visit localhost:8080. `/api/health` must return 200; `/hybrid/runs` must return
503 until runtime DB settings and AWS credentials are configured. GitHub Actions
also builds this image and runs these probes in `fullstack-container.yml`.
Local lint/build/tests alone do not verify a Linux container build.

For an actual inference smoke test, inject the five DB_* settings and HYBRID_*
settings described in `backend/HYBRID_DEPLOYMENT.md`. Use an EC2 instance role for
AWS access in production. Never bake `.env`, AWS keys or passwords into the image.

## Elastic Beanstalk on EC2

The account already has `pyroclast / Pyroclast-env` in `us-west-2`, currently a
Python-only environment on a t3.micro. The full app needs the **Docker running
Amazon Linux 2023** platform. Prepare a separate environment, for example
`Pyroclast-s3-env`, and test it before replacing or retiring the Python environment.
Do not change the existing Python platform in place.

1. Commit the Docker files, then produce a source bundle from committed files:

   ```sh
   python deploy/package_fullstack.py --out pyroclast-fullstack.zip
   ```

   This is cross-platform. Keep the ZIP outside the repository or remove it after
   upload. It exports tracked source from HEAD, not local `.env`, caches or virtual
   environments. The Dockerfile is at the ZIP root.

2. In Elastic Beanstalk, select application `pyroclast`, then create a **Web server**
   environment using the current supported **Docker / Amazon Linux 2023** branch.
   Upload the ZIP. Use **Single instance** for the first demo; no ELB is required.
   Start with t3.medium (4 GiB), a 30 GiB encrypted root disk, and monitor memory
   during build and first model load. This is a starting size, not load-tested
   capacity. Keep one inference worker. Review EC2, disk, public IPv4 and data
   transfer costs before launch; a second environment incurs additional cost.

3. Use a dedicated Pyroclast EC2 instance profile. Grant it read access to
   `pyroclast-ai-204898220304-us-west-2-an/models/flex2-hybrid/*` and access to the
   exact configuration secrets it needs. Do not expand the shared instance role
   used by the other applications. Keep model S3 objects private.

4. Set runtime environment variables:

   ```dotenv
   DB_HOST=<existing database endpoint>
   DB_PORT=5432
   DB_NAME=pyroclast
   DB_USER=<existing read-only database login>
   HYBRID_MODEL_NAME=flex2-hybrid
   HYBRID_S3_BUCKET=pyroclast-ai-204898220304-us-west-2-an
   HYBRID_S3_PREFIX=models/flex2-hybrid/
   AWS_REGION=us-west-2
   ```

   Set `DB_PASSWORD` using Beanstalk's runtime variable **Secrets Manager** or
   **SSM Parameter Store** source, rather than a committed configuration file.
   Set `DB_SSLMODE=verify-full` and
   `DB_SSLROOTCERT=/app/deploy/rds-ca-bundle.pem` for the existing database. The
   image ships its public CA bundle; Mac-local certificate paths do not exist in
   the container. Ensure
   the database permits traffic from this environment's security group on 5432.
   Database access should not be opened to all IP addresses. BACKEND_URL is fixed
   internally by the launcher; it is not a public backend URL in this layout.

5. Require IMDSv2 and allow hop limit 2 so the Docker bridge can receive instance
   credentials. After launch check the instance metadata options; if necessary:

   ```sh
   aws ec2 modify-instance-metadata-options --instance-id <new-instance-id> --http-tokens required --http-put-response-hop-limit 2 --region us-west-2
   ```

   Recheck after any Beanstalk instance replacement. Open only the web entry point
   to visitors; keep container/backend ports and database ports private. Beanstalk
   nginx routes the web entry point to the Dockerfile's exposed port 8080.

6. At the new environment's public hostname, verify:

   - `/` loads the frontend.
   - `/api/health` returns 200.
   - `/hybrid/runs` returns ready model metadata with `model.source = "s3"`.
   - Editing model inputs produces a selected flame; room Simulate succeeds.
   - Requests still work after stopping the Mac's local backend.

   The first hybrid request includes S3 download and warm-up. Do not treat a green
   health endpoint alone as proof that DB/S3 predictions work. Compare responses
   with the local API, then test model-unavailable handling and inspect logs.

7. Configure HTTPS before sharing for normal use. A custom domain can use a
   certificate on an HTTPS reverse proxy, or an AWS HTTPS entry point can be added
   in a follow-up deployment. A default single-instance Beanstalk HTTP hostname
   demonstrates public connectivity but does not supply application HTTPS.
   Do not retire the existing environment until the new URL and rollback are
   verified. An ELB is optional for this single-server demo, and useful later for
   managed HTTPS, health-based routing and multiple instances.

Official setup references:
[Docker images on Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/single-container-docker-configuration.html),
[runtime secrets](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.env-vars.html).

This repository prepares the deployment; no environment is created or public
deployment claimed by generating these files. An independent review and passing
container build should precede the live rollout.
