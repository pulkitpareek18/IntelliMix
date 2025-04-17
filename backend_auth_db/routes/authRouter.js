import { Router } from "express";
const router = Router();
import { login, logout } from "../controllers/authController.js";

router.get("/", (req, res) => {
  res.send("Hello from the Auth API!");
});

router.get("/login", login);
router.get("/logout", logout);

router.get("/signup", (req, res) => {
  res.send("Hello from the sign up API!");
});

export default router;