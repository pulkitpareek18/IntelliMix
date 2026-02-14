import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { colors } from '../utils/colors';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  link: string;
  color: string;
}

function FeatureCard({ icon, title, description, link, color }: FeatureCardProps) {
  const cardRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const card = cardRef.current;
    if (card) {
      const handleMouseMove = (e: MouseEvent) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const rotateX = (y - rect.height / 2) / 20;
        const rotateY = (rect.width / 2 - x) / 20;

        gsap.to(card, {
          rotateX: rotateX,
          rotateY: rotateY,
          duration: 0.5,
          ease: "power2.out",
        });
      };

      const handleMouseLeave = () => {
        gsap.to(card, {
          rotateX: 0,
          rotateY: 0,
          duration: 0.5,
          ease: "power2.out",
        });
      };

      card.addEventListener('mousemove', handleMouseMove);
      card.addEventListener('mouseleave', handleMouseLeave);

      return () => {
        card.removeEventListener('mousemove', handleMouseMove);
        card.removeEventListener('mouseleave', handleMouseLeave);
      };
    }
  }, []);

  // Determine the gradient color based on the card's theme color
  const getGradientColor = () => {
    // Use the passed color but ensure it's in the red/yellow theme
    if (color === colors.brightRed) {
      return `linear-gradient(to bottom right, white, ${colors.brightRed}15)`;
    } else if (color === colors.vibrantYellow) {
      return `linear-gradient(to bottom right, white, ${colors.vibrantYellow}15)`;
    } else if (color === colors.deepRed) {
      return `linear-gradient(to bottom right, white, ${colors.deepRed}15)`;
    } else {
      // Default fallback using the input color
      return `linear-gradient(to bottom right, white, ${color}15)`;
    }
  };

  return (
    <Link 
      ref={cardRef} 
      to={link} 
      className="block group rounded-2xl feature-card transform transition-all duration-300 hover:-translate-y-1 perspective-1000"
    >
      <div 
        className="bg-white backdrop-blur-sm rounded-2xl p-8 relative overflow-hidden h-full transition-all duration-300"
        style={{ 
          border: `1px solid ${color}30`,
          boxShadow: `0 0 15px ${color}20`
        }}
        onMouseEnter={(e) => {
          // Use the explicit gradient function to ensure correct colors
          e.currentTarget.style.background = getGradientColor();
          e.currentTarget.style.borderColor = `${color}60`;
          e.currentTarget.style.boxShadow = `0 0 25px ${color}30`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'white';
          e.currentTarget.style.borderColor = `${color}30`;
          e.currentTarget.style.boxShadow = `0 0 15px ${color}20`;
        }}
      >
        <div className="relative z-10">
          <div className="mb-4 transform transition-transform duration-300 ease-out group-hover:scale-110">
            <div style={{ color: color }} className="transition-colors duration-300">
              <div className="flex justify-center">
                {React.cloneElement(icon as React.ReactElement, {
                  className: "w-12 h-12"
                })}
              </div>
            </div>
          </div>
          <h3 
            className="text-xl font-semibold mb-2 transition-colors duration-300"
            style={{ color }}
          >
            {title}
          </h3>
          <p className="text-gray-700 group-hover:text-gray-900 transition-colors duration-300">
            {description}
          </p>
        </div>
      </div>
    </Link>
  );
}

export default FeatureCard;
