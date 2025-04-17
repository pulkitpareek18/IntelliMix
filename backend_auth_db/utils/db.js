import mongoose from "mongoose";

const connectDb = () => {
    mongoose.connect("mongodb+srv://pulkit:pulkit@cluster0.uiolkef.mongodb.net/intellimix")
        .then(()=>
        console.log("MongoDB connected successfully"))
        .catch(
            err=> console.error("MongoDB connection error:", err));
}

export default connectDb;