import { Router } from "express";
import { createUser, getAllUsers, getUser } from "../controllers/userController.js";
import auth_middleware from '../middlewares/auth_middleware.js';

const router = Router();

router.get("/", (req, res) => {
  res.send("Hello from the user API!");
});

router.post("/create", createUser)
router.get("/all", getAllUsers)
router.get("/me", auth_middleware, getUser)
    


export default router;