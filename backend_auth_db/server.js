import express from 'express';
import cors from 'cors';
import authRouter from './routes/authRouter.js';
import userRouter from './routes/userRouter.js';
import { Router } from 'express';
import connectDb from './utils/db.js';
import cookie_parser from 'cookie-parser';

const app = express();
const router = Router();

// Connect to the database
connectDb();

// Middleware to parse JSON bodies
app.use(express.json());
// Middleware to log requests
app.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});
// Middleware to handle errors
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});
// Middleware to serve static files
app.use(express.static('public'));
// Middleware to handle CORS
app.use(cors());
// Middleware to parse URL-encoded bodies
app.use(express.urlencoded({ extended: true }));
// Middleware to parse cookies
app.use(cookie_parser());


router.get('/api', (req, res) => {
  res.json({ message: 'Hello from the API!' });
});

// Middleware to use the routers
app.use('/auth', authRouter);
app.use('/user', userRouter);

app.get('/', (req, res) => {
  res.send('Hello, World!');
});




const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
}   );