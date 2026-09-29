import type { Request, Response, NextFunction } from 'express';

export function errorHandler(
  err: Error & { status?: number; statusCode?: number },
  req: Request,
  res: Response,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  next: NextFunction
) {
  const statusCode = err.statusCode || err.status || 500;
  console.error(`[STAMAS API Error] [${req.method} ${req.url}]`, err.message || err);

  return res.status(statusCode).json({
    success: false,
    message: err.message || 'An unexpected internal error occurred on the STAMAS server.'
  });
}
