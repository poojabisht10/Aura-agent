// Page 2: Contact Page
// Status: Created new (no similar component found)
//
// This component is unique to the Contact page. No match was found
// in the component library. It has been added to the library for
// potential reuse on future pages.

import React from 'react';

const ContactForm: React.FC = () => {
  return (
    <section className="w-full max-w-2xl mx-auto py-16 px-8">
      <h2 className="text-3xl font-bold text-[#111827] mb-2">Get in Touch</h2>
      <p className="text-base text-[#5F697A] mb-8">
        We would love to hear from you. Fill out the form below and we will get back to you shortly.
      </p>

      <form className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[#111827]">Name</label>
          <input
            type="text"
            placeholder="Your name"
            className="w-full px-4 py-3 rounded-lg border border-[#D1D5DB] text-base text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#1E40AF]"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[#111827]">Email</label>
          <input
            type="email"
            placeholder="you@example.com"
            className="w-full px-4 py-3 rounded-lg border border-[#D1D5DB] text-base text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#1E40AF]"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-[#111827]">Message</label>
          <textarea
            rows={4}
            placeholder="How can we help?"
            className="w-full px-4 py-3 rounded-lg border border-[#D1D5DB] text-base text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#1E40AF] resize-none"
          />
        </div>
        <button
          type="submit"
          className="bg-[#1E40AF] text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-[#1E3A8A] transition-colors self-start"
        >
          Send Message
        </button>
      </form>
    </section>
  );
};

export default ContactForm;
