Use `DEPLOYMENT_FREE_STACK.md` for the current v9 deployment flow.

Summary:

1. Push repo to GitHub public repo.
2. Add Neon `DATABASE_URL` to GitHub Actions secrets.
3. Run GitHub Actions workflow once to generate `backend/models/model_pack.joblib`.
4. Deploy backend on Koyeb Free with root directory `backend` and Dockerfile.
5. Deploy frontend on Netlify Free with base directory `frontend`.
6. Add `VITE_API_BASE_URL` in Netlify pointing to your Koyeb URL.
7. Set `ALLOWED_ORIGINS` in Koyeb to your Netlify URL.
