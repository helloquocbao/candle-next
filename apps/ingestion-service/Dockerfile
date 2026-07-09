FROM node:20.18.1-alpine3.20

WORKDIR /app

ENV NODE_ENV=production

# Copy package.json truoc de tan dung Docker layer caching cho npm install
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# Copy phan con lai cua source code
COPY . .

# Chạy bằng user không đặc quyền — "node" đã có sẵn trong image base.
USER node

CMD ["node", "src/index.js"]
