// Keep the shared implementation outside the frontend's ESM package so Vercel
// can compile it alongside the backend's CommonJS functions.
export { BOOK_FIELDS, parseBooksCSV, validateBooks, serializeBooksCSV } from '../../../shared/printedBooks.js'
