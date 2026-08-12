FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# We'll just run dev server for local compose
CMD ["npm", "run", "dev"]
