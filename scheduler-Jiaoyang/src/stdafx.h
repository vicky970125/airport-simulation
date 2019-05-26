﻿// stdafx.h : include file for standard system include files,
// or project specific include files that are used frequently, but
// are changed infrequently
//

#pragma once

#include <stdio.h>
#include <iostream>
#include <fstream>
// #include <tchar.h>
#include <vector>
 #include  <utility>
#include <assert.h> 

#include <google/dense_hash_map>

#include <boost/heap/fibonacci_heap.hpp>
#include <boost/graph/adjacency_list.hpp>
// boost graph helpers
// http://stackoverflow.com/questions/13453350/replace-bgl-iterate-over-vertexes-with-pure-c11-alternative

// Only for pairs of std::hash-able types for simplicity.
// You can of course template this struct to allow other hash functions
struct pair_hash {
	template <class T1, class T2>
	std::size_t operator () (const std::pair<T1, T2> &p) const {
		auto h1 = std::hash<T1>{}(p.first);
		auto h2 = std::hash<T2>{}(p.second);

		// Mainly for demonstration purposes, i.e. works but is overly simple
		// In the real world, use sth. like boost.hash_combine
		return h1 ^ h2;
	}
};


typedef boost::adjacency_list_traits<boost::vecS, boost::vecS, boost::bidirectionalS > searchGraphTraits_t;
typedef searchGraphTraits_t::vertex_descriptor vertex_t;
typedef searchGraphTraits_t::edge_descriptor edge_t;
typedef std::pair<double, double> position_t;

using std::vector;