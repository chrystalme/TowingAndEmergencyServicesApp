import 'package:flutter/material.dart';

import 'nearby_map_screen.dart';
import 'request_list_screen.dart';
import 'profile_screen.dart';

/// Post-login landing. Replaces the old statistics dashboard with the three
/// things a commuter actually does: see who is near them, see their jobs,
/// and manage their account.
///
/// Tab 0 is the map — the product's centre of gravity. Navigation happens
/// through the bottom bar; route pushes (e.g. /request, /driver) sit on top
/// of this shell so the back gesture always returns here.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin {
  late TabController _tabs;
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: TabBarView(
        controller: _tabs,
        children: [
          const NearbyMapScreen(),
          const RequestListScreen(),
          const ProfileScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: 'Map',
          ),
          const NavigationDestination(
            icon: Icon(Icons.inbox_outlined),
            selectedIcon: Icon(Icons.inbox),
            label: 'My Requests',
          ),
          const NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
        onDestinationSelected: (index) {
          setState(() => _selectedIndex = index);
          _tabs.animateTo(index);
        },
      ),
    );
  }
}