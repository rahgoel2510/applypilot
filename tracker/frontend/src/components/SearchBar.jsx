import { Search } from 'lucide-react';

export default function SearchBar({
  search,
  onSearchChange,
  company,
  onCompanyChange,
  sort,
  onSortChange,
  companies,
  totalJobs,
  filteredJobs,
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-[#DCE5ED] bg-white p-2.5 shadow-sm">
      {/* Search input */}
      <label className="relative min-w-[220px] flex-1">
        <span className="sr-only">Search jobs</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8291A5]" />
        <input
          type="search"
          placeholder="Search jobs or companies"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-9 w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] pl-9 pr-3 text-sm text-[#203A5F] outline-none transition-colors placeholder:text-[#9AA8B8] focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
        />
      </label>

      {/* Company filter */}
      <label>
        <span className="sr-only">Filter by company</span>
        <select
          value={company}
          onChange={(e) => onCompanyChange(e.target.value)}
          className="h-9 max-w-[180px] rounded-lg border border-[#DCE5ED] bg-white px-3 text-sm text-[#52677F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1]"
        >
          <option value="all">All companies</option>
          {companies.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      {/* Sort */}
      <label>
        <span className="sr-only">Sort jobs</span>
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-9 rounded-lg border border-[#DCE5ED] bg-white px-3 text-sm text-[#52677F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1]"
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </label>

      {/* Count */}
      <span className="ml-auto px-1 text-xs text-[#8291A5]">
        {filteredJobs} of {totalJobs}
      </span>
    </div>
  );
}
