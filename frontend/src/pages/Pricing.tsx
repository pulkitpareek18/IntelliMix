import React from 'react';

// Use the color theme from App.tsx
const colors = {
  brightRed: "#f4483a",       // Primary accent
  slightlyDarkerRed: "#f45444", // Secondary accent
  deepRed: "#d24d34",         // Emphasis/CTA
  reddishOrange: "#d14324",   // Highlight
  vividRed: "#f13521",        // Attention-grabbing
  vibrantYellow: "#ffb92b",   // Buttons/highlights
  softYellow: "#f7e5a0",      // Subtle background
  paleYellow: "#ffe09c",      // Secondary background
  white: "#FFFFFF",
  black: "#000000",
  softRed: "#fee2e1",         // Very light red background
  softerRed: "#fbeae9",       // Even lighter red for larger areas
  textDark: "#444444"         // Softer than pure black for text
};

const plans = [
  {
    name: 'Free',
    price: '$0',
    description: 'Basic features for personal use',
    features: ['Access to limited features', 'Basic support', 'Community access'],
    buttonText: 'Get Started',
    color: colors.softRed,
    buttonColor: colors.brightRed,
    buttonHoverColor: colors.deepRed,
    borderColor: colors.brightRed,
  },
  {
    name: 'Individual',
    price: '$9.99/mo',
    description: 'Advanced features for individuals',
    features: ['All Free features', 'Priority support', 'Customizable dashboard'],
    buttonText: 'Subscribe Now',
    color: colors.paleYellow,
    buttonColor: colors.vibrantYellow,
    buttonHoverColor: colors.softYellow,
    borderColor: colors.vibrantYellow,
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Contact Us',
    description: 'Comprehensive solutions for teams',
    features: ['All Individual features', 'Dedicated account manager', 'Premium support'],
    buttonText: 'Contact Sales',
    color: colors.softRed,
    buttonColor: colors.brightRed,
    buttonHoverColor: colors.deepRed,
    borderColor: colors.brightRed,
  },
];

const PricingCard = ({ plan }) => (
  <div 
    className={`rounded-2xl p-6 transition-all duration-300 backdrop-blur-sm ${plan.featured ? 'transform hover:scale-105' : 'hover:shadow-lg'}`}
    style={{ 
      border: `2px solid ${plan.borderColor}30`,
      background: `${plan.color}20`,
      boxShadow: plan.featured ? `0 10px 25px -5px ${plan.borderColor}30` : 'none'
    }}
  >
    {plan.featured && (
      <div 
        className="absolute top-0 right-0 transform translate-x-1/4 -translate-y-1/4 rotate-12 px-4 py-1 rounded-full text-sm font-bold"
        style={{ backgroundColor: colors.vibrantYellow, color: colors.white }}
      >
        Popular
      </div>
    )}
    <h3 className="text-2xl font-semibold mb-2" style={{ color: plan.borderColor }}>{plan.name}</h3>
    <p className="text-3xl font-bold mb-2" style={{ color: colors.textDark }}>{plan.price}</p>
    <p className="text-gray-600 mb-6">{plan.description}</p>
    <ul className="space-y-3 mb-6">
      {plan.features.map((feature, index) => (
        <li key={index} className="flex items-start">
          <span 
            className="inline-block w-5 h-5 mr-2 mt-0.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: `${plan.borderColor}20` }}
          >
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
              style={{ color: plan.borderColor }}
              className="w-full h-full p-1"
            >
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </span>
          <span style={{ color: colors.textDark }}>{feature}</span>
        </li>
      ))}
    </ul>
    <button 
      className="w-full py-3 text-white rounded-xl transition-colors duration-300 font-medium"
      style={{ 
        backgroundColor: plan.buttonColor,
        boxShadow: `0 4px 12px ${plan.buttonColor}50`
      }}
      onMouseOver={(e) => { e.currentTarget.style.backgroundColor = plan.buttonHoverColor }}
      onMouseOut={(e) => { e.currentTarget.style.backgroundColor = plan.buttonColor }}
    >
      {plan.buttonText}
    </button>
  </div>
);

const PricingPage = () => (
  <div className="min-h-screen py-16 relative overflow-hidden" style={{ background: 'transparent' }}>
    {/* Background decorative elements */}
    <div 
      className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-20 blur-3xl -z-10" 
      style={{ backgroundColor: colors.brightRed }}
    ></div>
    <div 
      className="absolute bottom-0 left-0 w-80 h-80 rounded-full opacity-20 blur-3xl -z-10" 
      style={{ backgroundColor: colors.vibrantYellow }}
    ></div>
    
    <div className="max-w-5xl mx-auto text-center mb-12">
      <h1 className="text-5xl font-bold mb-4" style={{ color: colors.deepRed }}>Our Pricing Plans</h1>
      <div className="w-24 h-1 mx-auto rounded-full mb-4" style={{ backgroundColor: colors.vibrantYellow }}></div>
      <p className="text-lg text-gray-600 max-w-2xl mx-auto">
        Choose the plan that best fits your needs and unlock the full potential of IntelliMix.
      </p>
    </div>
    
    <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8 px-4 relative">
      {plans.map((plan, index) => (
        <div key={index} className={`${plan.featured ? 'relative' : ''}`}>
          <PricingCard plan={plan} />
        </div>
      ))}
    </div>
    
    <div className="max-w-3xl mx-auto mt-16 text-center px-4">
      <h3 className="text-2xl font-semibold mb-4" style={{ color: colors.deepRed }}>Need Something Custom?</h3>
      <p className="text-gray-600 mb-6">
        We offer tailored solutions for specific requirements. 
        Contact our sales team to discuss a customized plan that meets your needs.
      </p>
      <button 
        className="py-3 px-8 rounded-xl text-white font-medium transition-colors duration-300"
        style={{ 
          backgroundColor: colors.deepRed,
          boxShadow: `0 4px 12px ${colors.deepRed}40`
        }}
        onMouseOver={(e) => { e.currentTarget.style.backgroundColor = colors.vividRed }}
        onMouseOut={(e) => { e.currentTarget.style.backgroundColor = colors.deepRed }}
      >
        Contact Sales Team
      </button>
    </div>
  </div>
);

export default PricingPage;
