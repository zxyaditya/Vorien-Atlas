const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Use API_PROXY_TARGET if set (e.g. inside Docker network), otherwise fallback to local host
  const target = process.env.API_PROXY_TARGET || 'http://localhost:8000';
  app.use(
    '/api',
    createProxyMiddleware({
      target: target,
      changeOrigin: true,
      proxyTimeout: 600000,
      timeout: 600000,
    })
  );
};
