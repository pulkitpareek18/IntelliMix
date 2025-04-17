const auth_middleware = (req, res, next) => {
    if (!req.cookies.auth_token || req.cookies.auth_token === 'undefined') {
        return res.status(401).json({ message: 'Unauthorized' });
    }
    next();
};

export default auth_middleware;