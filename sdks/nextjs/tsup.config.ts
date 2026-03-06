import { defineConfig } from 'tsup'

export default defineConfig({
  entry: ['src/index.ts', 'src/middleware.ts', 'src/server.ts'],
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  external: ['next', 'next/server', 'react', '@sentinel-auth/js', '@sentinel-auth/react', 'jose'],
})
