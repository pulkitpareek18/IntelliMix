import React from 'react';
import { Link } from 'react-router-dom';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  link: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon, title, description, link }) => {
  return (
    <div className="bg-gray-800 p-6 rounded-lg shadow-lg hover:shadow-xl transition-shadow duration-300">
      <div className="flex items-center justify-center w-16 h-16 bg-gray-700 rounded-full mb-4">
        {icon}
      </div>
      <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
      <p className="text-gray-400 mb-4">{description}</p>
      <Link
        to={link}
        className="text-cyan-400 hover:text-cyan-300 transition-colors duration-200"
      >
        Learn More →
      </Link>
    </div>
  );
};

export default FeatureCard;