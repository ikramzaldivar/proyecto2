import 'dotenv/config';
import { z } from 'zod';

/**
 * Valida las variables de entorno usadas por la aplicación.
 */
const envSchema = z
  .object({
    NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),

    PORT: z.coerce.number().int().positive().default(3000),

    DATABASE_URL: z.string().min(1),

    STORAGE_PROVIDER: z.enum(['minio', 's3']).default('minio'),

    MINIO_ENDPOINT: z.string().min(1).optional(),

    MINIO_PORT: z.coerce.number().int().positive().default(9000),

    MINIO_USE_SSL: z
      .enum(['true', 'false'])
      .default('false')
      .transform((value) => value === 'true'),

    MINIO_ACCESS_KEY: z.string().min(1).optional(),

    MINIO_SECRET_KEY: z.string().min(1).optional(),

    MINIO_BUCKET: z.string().min(3).optional(),

    AWS_REGION: z.string().min(1).default('us-east-2'),

    S3_BUCKET: z.string().min(3).optional(),

    MAX_UPLOAD_SIZE_BYTES: z.coerce
      .number()
      .int()
      .positive()
      .default(5 * 1024 * 1024),
  })
  .superRefine((value, context) => {
    if (value.STORAGE_PROVIDER === 'minio') {
      for (const field of [
        'MINIO_ENDPOINT',
        'MINIO_ACCESS_KEY',
        'MINIO_SECRET_KEY',
        'MINIO_BUCKET',
      ] as const) {
        if (!value[field]) {
          context.addIssue({
            code: 'custom',
            path: [field],
            message: `${field} es obligatoria cuando STORAGE_PROVIDER=minio.`,
          });
        }
      }
    }

    if (value.STORAGE_PROVIDER === 's3' && !value.S3_BUCKET) {
      context.addIssue({
        code: 'custom',
        path: ['S3_BUCKET'],
        message: 'S3_BUCKET es obligatoria cuando STORAGE_PROVIDER=s3.',
      });
    }
  });

/**
 * Variables ya validadas y tipadas.
 * Si alguna configuración requerida falta, la aplicación falla al iniciar.
 */
export const env = envSchema.parse(process.env);
