import User from "../models/user.js";
import jwt from "jsonwebtoken";

const login = async (req, res) => {
    const { email, password } = req.body;
    const user = await User.findOne({ email, password });
    if (!user) {
        return res.status(401).json({ message: "Invalid credentials" });
    }
    const token = jwt.sign({ id: user._id , email: user.email}, "secretkey", {
        expiresIn: "1h",
    });
    return res.cookie("auth_token", token, {
        httpOnly: true,
        secure: false,
    }).status(200).json({ message: "Login successful" });
    
}

const logout = async (req, res) => {
    res.clearCookie("auth_token").status(200).json({ message: "Logout successful" });
}

export { login, logout };