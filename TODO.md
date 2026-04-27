# Reddit Scraper — TODO

## 🔴 Alta prioridad

- [ ] 1. Configurar PostgreSQL en Dokploy y conectar via DATABASE_URL
- [ ] 2. Crear app en Dokploy y conectar repo github.com/MauroBeltranM/reddit-scraper
- [ ] 3. Configurar Cloudflare tunnel: reddit.maurobeltranmarcos.com → puerto del container
- [ ] 4. Hacer el scrape asíncrono (FastAPI BackgroundTasks o Celery) — ahora bloquea el endpoint hasta 3 min
- [ ] 5. Añadir progreso de scrapeo en tiempo real (SSE o polling) para que la UI no se quede colgada

## 🟡 Media prioridad

- [ ] 6. Paginación real en la lista de posts (offset/limit ya existe en API, falta en el frontend)
- [ ] 7. Paginación en lista de comments del post detail (cargar más al scroll)
- [ ] 8. Cron automático: scrape periódico de subreddits activos (APScheduler en backend)
- [ ] 9. Ajustar límites configurables: max_new_posts, TOP_COMMENTS, REQUEST_DELAY desde la UI o env vars
- [ ] 10. Guardar más snapshots: si se re-scrapea un post existente, crear snapshot nuevo para ver evolución del score

## 🟢 Mejoras de UI/UX

- [ ] 11. Dashboard con gráficos: posts por subreddit, score distribution, scraping timeline
- [ ] 12. Vista de subreddit detail: stats del subreddit, posts asociados, último scrape, frecuencia
- [ ] 13. Indicador de carga visual durante scrapeo (spinner + mensajes de progreso "Scraping post 3/10...")
- [ ] 14. Modo compacto/denso en lista de posts para ver más de golpe
- [ ] 15. Colapsar/expandir hilos de comments individualmente

## 🔵 Funcionalidades nuevas

- [ ] 16. Buscar posts por título (no solo comments)
- [ ] 17. Exportar datos: CSV/JSON de posts o comments de un subreddit
- [ ] 18. Añadir subreddit con filtro de timeframe (hot, new, top-day, top-week, top-all)
- [ ] 19. Guardar imágenes/thumbnails de los posts (tipo image) en disco o S3
- [ ] 20. API key de Reddit (OAuth) para subir rate limits y evitar bloqueos — con toggle en la UI

---

**Notas:**
- El repo está en github.com/MauroBeltranM/reddit-scraper (branch main)
- Frontend: Vue 3 + Vue Router + Axios
- Backend: FastAPI + SQLAlchemy + httpx
- Para deploy: Dokploy, dominio reddit.maurobeltranmarcos.com
- SQLite funciona para desarrollo, PostgreSQL obligatorio para producción
