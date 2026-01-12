"""
Acronym Expansion Handler

Handles acronym expansion in entity resolution searches.
Searches on both the acronym and its expanded form(s) to improve
both recall (finding more matches) and precision (better disambiguation).

Use Cases:
- Hardware: ESR -> Exception Status Register, Exception State Register
- Medical: MI -> Myocardial Infarction
- Legal: SLA -> Service Level Agreement
- Business: ROI -> Return on Investment
"""

from typing import List, Dict, Set, Optional, Union


class AcronymExpansionHandler:
    """
    Expands acronyms to their full forms for improved entity resolution.
    
    This handler improves both recall and precision by:
    - Recall: Finding matches under different forms (short and long)
    - Precision: Using expanded form for better semantic disambiguation
    
    Attributes:
        acronym_dict (Dict[str, List[str]]): Maps acronyms to their expansions
        case_sensitive (bool): Whether acronym matching is case-sensitive
        expansion_strategy (str): How to combine results ('union', 'intersection', 'ranked')
    
    Example:
        >>> handler = AcronymExpansionHandler({
        ...     'ESR': ['Exception Status Register', 'Exception State Register'],
        ...     'ALU': ['Arithmetic Logic Unit'],
        ...     'MMU': ['Memory Management Unit']
        ... })
        >>> 
        >>> terms = handler.expand_search_terms('ESR')
        >>> print(terms)
        ['ESR', 'Exception Status Register', 'Exception State Register']
    """
    
    def __init__(
        self,
        acronym_dict: Dict[str, Union[str, List[str]]],
        case_sensitive: bool = False,
        expansion_strategy: str = 'union'
    ):
        """
        Initialize the Acronym Expansion Handler.
        
        Args:
            acronym_dict: Maps acronyms to expansions. Values can be string or list of strings.
                         Example: {'ESR': 'Exception Status Register'} or
                                 {'ESR': ['Exception Status Register', 'Exception State Register']}
            case_sensitive: If False, normalizes acronyms to uppercase for matching
            expansion_strategy: How to handle results from multiple terms:
                              - 'union': Combine all results (default, best recall)
                              - 'intersection': Only results found under all forms (best precision)
                              - 'ranked': Rank by how many forms matched
        
        Raises:
            ValueError: If expansion_strategy is not recognized
        """
        if expansion_strategy not in ('union', 'intersection', 'ranked'):
            raise ValueError(
                f"expansion_strategy must be 'union', 'intersection', or 'ranked', "
                f"got '{expansion_strategy}'"
            )
        
        # Normalize the acronym dictionary
        self.acronym_dict = {}
        for key, value in acronym_dict.items():
            # Normalize key based on case_sensitive setting
            normalized_key = key if case_sensitive else key.upper()
            
            # Ensure value is a list
            if isinstance(value, str):
                self.acronym_dict[normalized_key] = [value]
            else:
                self.acronym_dict[normalized_key] = list(value)
        
        self.case_sensitive = case_sensitive
        self.expansion_strategy = expansion_strategy
    
    def is_acronym(self, term: str) -> bool:
        """
        Check if a term is a known acronym.
        
        Args:
            term: Term to check
        
        Returns:
            True if term is in the acronym dictionary
        
        Example:
            >>> handler = AcronymExpansionHandler({'ESR': 'Exception Status Register'})
            >>> handler.is_acronym('ESR')
            True
            >>> handler.is_acronym('esr')  # Case-insensitive by default
            True
            >>> handler.is_acronym('UNKNOWN')
            False
        """
        lookup_term = term if self.case_sensitive else term.upper()
        return lookup_term in self.acronym_dict
    
    def get_expansions(self, acronym: str) -> List[str]:
        """
        Get all known expansions for an acronym.
        
        Args:
            acronym: Acronym to expand
        
        Returns:
            List of expanded forms, empty list if not found
        
        Example:
            >>> handler = AcronymExpansionHandler({
            ...     'ESR': ['Exception Status Register', 'Exception State Register']
            ... })
            >>> handler.get_expansions('ESR')
            ['Exception Status Register', 'Exception State Register']
        """
        lookup_term = acronym if self.case_sensitive else acronym.upper()
        return self.acronym_dict.get(lookup_term, []).copy()
    
    def expand_search_terms(self, term: str, include_original: bool = True) -> List[str]:
        """
        Expand a search term to include all known forms.
        
        Args:
            term: Search term (may be acronym or regular term)
            include_original: Whether to include the original term in results
        
        Returns:
            List of search terms (original + expansions if acronym)
        
        Example:
            >>> handler = AcronymExpansionHandler({
            ...     'ESR': ['Exception Status Register', 'Exception State Register']
            ... })
            >>> handler.expand_search_terms('ESR')
            ['ESR', 'Exception Status Register', 'Exception State Register']
            >>> handler.expand_search_terms('NOT_AN_ACRONYM')
            ['NOT_AN_ACRONYM']
        """
        result = []
        
        if include_original:
            result.append(term)
        
        if self.is_acronym(term):
            expansions = self.get_expansions(term)
            result.extend(expansions)
        
        return result
    
    def expand_batch(
        self,
        terms: List[str],
        include_original: bool = True
    ) -> Dict[str, List[str]]:
        """
        Expand multiple terms at once.
        
        Args:
            terms: List of terms to expand
            include_original: Whether to include original terms
        
        Returns:
            Dict mapping each term to its expanded forms
        
        Example:
            >>> handler = AcronymExpansionHandler({
            ...     'ESR': ['Exception Status Register'],
            ...     'ALU': ['Arithmetic Logic Unit']
            ... })
            >>> handler.expand_batch(['ESR', 'ALU', 'OTHER'])
            {
                'ESR': ['ESR', 'Exception Status Register'],
                'ALU': ['ALU', 'Arithmetic Logic Unit'],
                'OTHER': ['OTHER']
            }
        """
        return {
            term: self.expand_search_terms(term, include_original)
            for term in terms
        }
    
    def add_acronym(self, acronym: str, expansions: Union[str, List[str]]):
        """
        Add a new acronym or update an existing one.
        
        Args:
            acronym: Acronym to add
            expansions: Expansion(s) for the acronym
        
        Example:
            >>> handler = AcronymExpansionHandler({})
            >>> handler.add_acronym('CPU', 'Central Processing Unit')
            >>> handler.add_acronym('PC', ['Program Counter', 'Personal Computer'])
        """
        normalized_key = acronym if self.case_sensitive else acronym.upper()
        
        if isinstance(expansions, str):
            self.acronym_dict[normalized_key] = [expansions]
        else:
            self.acronym_dict[normalized_key] = list(expansions)
    
    def remove_acronym(self, acronym: str) -> bool:
        """
        Remove an acronym from the dictionary.
        
        Args:
            acronym: Acronym to remove
        
        Returns:
            True if acronym was removed, False if not found
        
        Example:
            >>> handler = AcronymExpansionHandler({'ESR': 'Exception Status Register'})
            >>> handler.remove_acronym('ESR')
            True
            >>> handler.remove_acronym('NOT_FOUND')
            False
        """
        normalized_key = acronym if self.case_sensitive else acronym.upper()
        
        if normalized_key in self.acronym_dict:
            del self.acronym_dict[normalized_key]
            return True
        return False
    
    def get_all_acronyms(self) -> List[str]:
        """
        Get list of all known acronyms.
        
        Returns:
            List of acronym keys
        
        Example:
            >>> handler = AcronymExpansionHandler({
            ...     'ESR': 'Exception Status Register',
            ...     'ALU': 'Arithmetic Logic Unit'
            ... })
            >>> sorted(handler.get_all_acronyms())
            ['ALU', 'ESR']
        """
        return list(self.acronym_dict.keys())
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get statistics about the acronym dictionary.
        
        Returns:
            Dict with counts and distribution info
        
        Example:
            >>> handler = AcronymExpansionHandler({
            ...     'ESR': ['Exception Status Register', 'Exception State Register'],
            ...     'ALU': ['Arithmetic Logic Unit']
            ... })
            >>> stats = handler.get_statistics()
            >>> stats['total_acronyms']
            2
            >>> stats['total_expansions']
            3
        """
        total_acronyms = len(self.acronym_dict)
        total_expansions = sum(len(expansions) for expansions in self.acronym_dict.values())
        
        # Count how many acronyms have multiple expansions
        multi_expansion_count = sum(
            1 for expansions in self.acronym_dict.values()
            if len(expansions) > 1
        )
        
        # Get max expansions for any single acronym
        max_expansions = max(
            (len(expansions) for expansions in self.acronym_dict.values()),
            default=0
        )
        
        return {
            'total_acronyms': total_acronyms,
            'total_expansions': total_expansions,
            'avg_expansions_per_acronym': total_expansions / total_acronyms if total_acronyms > 0 else 0,
            'multi_expansion_count': multi_expansion_count,
            'max_expansions': max_expansions,
            'case_sensitive': self.case_sensitive,
            'expansion_strategy': self.expansion_strategy
        }
    
    @classmethod
    def from_file(cls, filepath: str, case_sensitive: bool = False) -> 'AcronymExpansionHandler':
        """
        Load acronym dictionary from a file.
        
        File format (JSON):
        {
            "ESR": ["Exception Status Register", "Exception State Register"],
            "ALU": "Arithmetic Logic Unit",
            "MMU": "Memory Management Unit"
        }
        
        Args:
            filepath: Path to JSON file containing acronym dictionary
            case_sensitive: Whether matching should be case-sensitive
        
        Returns:
            AcronymExpansionHandler instance
        
        Example:
            >>> handler = AcronymExpansionHandler.from_file('acronyms.json')
        """
        import json
        
        with open(filepath, 'r') as f:
            acronym_dict = json.load(f)
        
        return cls(acronym_dict, case_sensitive=case_sensitive)
    
    def to_file(self, filepath: str):
        """
        Save acronym dictionary to a file.
        
        Args:
            filepath: Path where to save the dictionary (JSON format)
        
        Example:
            >>> handler = AcronymExpansionHandler({'ESR': 'Exception Status Register'})
            >>> handler.to_file('my_acronyms.json')
        """
        import json
        
        with open(filepath, 'w') as f:
            json.dump(self.acronym_dict, f, indent=2)

