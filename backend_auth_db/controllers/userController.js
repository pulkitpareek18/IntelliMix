import User from '../models/user.js';
import jwt from 'jsonwebtoken';

const createUser = async (req, res) => {
    try {
        const { name, email, password } = req.body;
        const newUser = new User({ name, email, password });
        await newUser.save();
        const token = jwt.sign({ id: newUser._id , email: newUser.email}, "secretkey", {
                expiresIn: "1h",
        });
        return res.cookie("auth_token", token, {
                httpOnly: true,
                secure: false,
        }).status(201).json({ message: "User Created Successfully!" });
    } catch (error) {
        res.status(500).json({ message: 'Error creating user', error });
    }
}

const getAllUsers = async (req, res) => {
    try {
        const users = await User.find();
        res.status(200).json(users);
    }
    catch (error) {
        res.status(500).send("Error", error)
    }
}

const getUser = async (req, res) => {
    const token = req.cookies.auth_token;
    const decoded = jwt.verify(token, 'secretkey')
    const email = decoded.email;
    const user = await User.find({ email: email });
    return res.status(200).json({ user });
}

export { createUser, getAllUsers, getUser };